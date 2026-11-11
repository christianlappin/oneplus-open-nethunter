/* SPDX-License-Identifier: GPL-2.0-only */
/* Experimental management-only monitor TX. Default disabled. */
#include <linux/module.h>
#include <linux/etherdevice.h>
#include <linux/workqueue.h>
#include "wlan_hdd_includes.h"
#include "wlan_hdd_main.h"
#include "wlan_hdd_object_manager.h"
#include "wlan_hdd_nh_tx.h"
#include "wlan_hdd_nh_radiotap.h"
#include "wlan_hdd_nh_policy.h"
#include "osif_vdev_sync.h"
#include "wlan_vdev_mlme_api.h"
#include "wlan_objmgr_peer_obj.h"
#include "cds_packet.h"
#include "wma_types.h"
#include "wlan_cfg80211_p2p.h"
#include "wlan_p2p_ucfg_api.h"
#include "wlan_p2p_public_struct.h"
#include "wlan_mlme_ucfg_api.h"
#include <linux/rtnetlink.h>
#include <linux/completion.h>
#include <linux/mutex.h>

#define NH_QUEUE_LIMIT 32
#define NH_INFLIGHT_LIMIT 8
static struct sk_buff_head nh_queue = {
	.next = (struct sk_buff *)&nh_queue,
	.prev = (struct sk_buff *)&nh_queue,
	.lock = __SPIN_LOCK_UNLOCKED(nh_queue.lock),
};
static bool nh_closing = true;
static unsigned int nh_tx_mode; /* 0: disabled, 1: dry-run, 2: firmware TX */
/* Immutable for a module lifetime: no configuration changes under live vdevs. */
static unsigned int nh_tx_backend;
static bool nh_random_sa;
static bool nh_raw_frames;
module_param_named(nh_monitor_raw_frames, nh_raw_frames, bool, 0400);
MODULE_PARM_DESC(nh_monitor_raw_frames, "Enable experimental data and RTS transmission on the station backend");
module_param_named(nh_monitor_random_sa, nh_random_sa, bool, 0400);
MODULE_PARM_DESC(nh_monitor_random_sa, "Explicit station-backend opt-in for valid unicast source MACs used by aireplay-ng tests");
module_param_named(nh_monitor_tx_backend, nh_tx_backend, uint, 0400);
MODULE_PARM_DESC(nh_monitor_tx_backend, "0 legacy monitor WMA (diagnostic), 1 host-managed station/P2P management path");
static unsigned long nh_sta_next_tx;
static atomic64_t nh_sta_queued = ATOMIC64_INIT(0);
static DEFINE_MUTEX(nh_stop_mutex);
static DECLARE_COMPLETION(nh_stop_ack);
static unsigned int nh_stopping_vdev = ~0U;
static int nh_sta_last_errno;
module_param_named(nh_monitor_sta_last_errno, nh_sta_last_errno, int, 0400);

static void nh_tx_worker(struct work_struct *work);
static DECLARE_WORK(nh_work, nh_tx_worker);

bool hdd_nh_sta_backend_enabled(void)
{
	return nh_tx_backend == 1;
}

void hdd_nh_monitor_stop_ack(unsigned int vdev_id)
{
	if (READ_ONCE(nh_stopping_vdev) == vdev_id)
		complete(&nh_stop_ack);
}

int hdd_nh_stop_monitor(struct net_device *dev)
{
	struct hdd_adapter *adapter = WLAN_HDD_GET_PRIV_PTR(dev);
	struct wlan_objmgr_vdev *vdev;
	int result = 0;

	if (!hdd_nh_sta_backend_enabled())
		return 0;
	WRITE_ONCE(nh_tx_mode, 0);
	flush_work(&nh_work);
	vdev = hdd_objmgr_get_vdev_by_user(adapter, WLAN_DP_ID);
	if (!vdev)
		return 0;
	mutex_lock(&nh_stop_mutex);
	if (QDF_IS_STATUS_SUCCESS(wlan_vdev_is_up_active_state(vdev))) {
		reinit_completion(&nh_stop_ack);
		WRITE_ONCE(nh_stopping_vdev, adapter->vdev_id);
		/* Stop while the host object is still CREATED. Deleting first
		 * races the STOP response timer and the object's DELETE timer.
		 */
		if (QDF_IS_STATUS_ERROR(wlan_vdev_mlme_sm_deliver_evt(vdev,
						WLAN_VDEV_SM_EV_DOWN, 0, NULL)))
			result = -EIO;
		else if (!wait_for_completion_timeout(&nh_stop_ack,
						      msecs_to_jiffies(3000)))
			result = -ETIMEDOUT;
		WRITE_ONCE(nh_stopping_vdev, ~0U);
	}
	mutex_unlock(&nh_stop_mutex);
	hdd_objmgr_put_vdev_by_user(vdev, WLAN_DP_ID);
	return result;
}

static int nh_frequency_set(const char *value, const struct kernel_param *kp)
{
	unsigned int frequency;
	int result = kstrtouint(value, 0, &frequency);

	if (result)
		return result;
	if (!hdd_nh_sta_backend_enabled() || READ_ONCE(nh_tx_mode))
		return -EBUSY;
	return hdd_nh_set_monitor_frequency(frequency);
}

static const struct kernel_param_ops nh_frequency_ops = {.set = nh_frequency_set};
module_param_cb(nh_monitor_frequency, &nh_frequency_ops, NULL, 0200);
static atomic_t nh_inflight = ATOMIC_INIT(0);
static atomic64_t nh_rejected = ATOMIC64_INIT(0);
static atomic64_t nh_dry_run = ATOMIC64_INIT(0);
static atomic64_t nh_submitted = ATOMIC64_INIT(0);
static atomic64_t nh_submit_error = ATOMIC64_INIT(0);
static atomic64_t nh_fw_ok = ATOMIC64_INIT(0);
static atomic64_t nh_fw_error = ATOMIC64_INIT(0);
static unsigned int nh_last_reject;
static unsigned int nh_last_freq;
static unsigned int nh_last_fw_status = ~0U;
module_param_named(nh_monitor_tx_last_fw_status, nh_last_fw_status, uint, 0400);
module_param_named(nh_monitor_tx_last_freq, nh_last_freq, uint, 0400);
module_param_named(nh_monitor_tx_last_reject, nh_last_reject, uint, 0400);
MODULE_PARM_DESC(nh_monitor_tx_last_reject, "Last rejection stage: 1 initial, 2 flags/global mode, 3 sync, 4 context, 5 vdev, 6 policy, 7 pdev, 8 self peer, 9 destination peer, 10 channel, 11 WMA, 12 inflight, 13 allocation, 14 submit, 25 admission, 26 queue");

static int nh_mode_set(const char *value, const struct kernel_param *kp)
{
	unsigned int mode;
	int result = kstrtouint(value, 0, &mode);

	if (result)
		return result;
	if (mode > 2)
		return -EINVAL;
	WRITE_ONCE(nh_tx_mode, mode);
	/* Wait out a running submission when disabling. Frames already owned
	 * by firmware may still complete; inflight reports that separately.
	 */
	if (!mode)
		flush_work(&nh_work);
	return 0;
}

static int nh_mode_get(char *buffer, const struct kernel_param *kp)
{
	return scnprintf(buffer, PAGE_SIZE, "%u\n", READ_ONCE(nh_tx_mode));
}

static const struct kernel_param_ops nh_mode_ops = {
	.set = nh_mode_set,
	.get = nh_mode_get,
};
module_param_cb(nh_monitor_tx_mode, &nh_mode_ops, NULL, 0600);
MODULE_PARM_DESC(nh_monitor_tx_mode, "0 disabled (default), 1 validation only, 2 experimental firmware TX");

static int nh_stats_get(char *buffer, const struct kernel_param *kp)
{
	return scnprintf(buffer, PAGE_SIZE,
		"mode=%u closing=%u queued=%u inflight=%d rejected=%lld dry_run=%lld submitted=%lld submit_error=%lld fw_status_ok=%lld fw_status_error=%lld sta_queued=%lld\n",
		READ_ONCE(nh_tx_mode), READ_ONCE(nh_closing),
		skb_queue_len(&nh_queue), atomic_read(&nh_inflight),
		atomic64_read(&nh_rejected), atomic64_read(&nh_dry_run),
		atomic64_read(&nh_submitted), atomic64_read(&nh_submit_error),
		atomic64_read(&nh_fw_ok), atomic64_read(&nh_fw_error),
		atomic64_read(&nh_sta_queued));
}

static const struct kernel_param_ops nh_stats_ops = { .get = nh_stats_get };
module_param_cb(nh_monitor_tx_stats, &nh_stats_ops, NULL, 0400);

static int nh_rx_state_get(char *buffer, const struct kernel_param *kp)
{
	return hdd_nh_get_monitor_rx_state(buffer);
}

static const struct kernel_param_ops nh_rx_state_ops = {
	.get = nh_rx_state_get,
};
module_param_cb(nh_monitor_rx_state, &nh_rx_state_ops, NULL, 0400);

static int nh_rx_refresh_set(const char *value, const struct kernel_param *kp)
{
	unsigned int requested;
	int result = kstrtouint(value, 0, &requested);

	if (result)
		return result;
	if (requested != 1 || READ_ONCE(nh_tx_mode))
		return -EINVAL;
	return hdd_nh_refresh_monitor_rx();
}

static const struct kernel_param_ops nh_rx_refresh_ops = {
	.set = nh_rx_refresh_set,
};
module_param_cb(nh_monitor_refresh_rx, &nh_rx_refresh_ops, NULL, 0200);

/* The mgmt descriptor owns the QDF packet on successful submission. Its
 * completion handler unmaps DMA before calling us, then releases its peer
 * reference afterwards. A firmware status is not independent RF evidence.
 */
static QDF_STATUS nh_ota_complete(void *context, qdf_nbuf_t packet,
				uint32_t status, void *params)
{
	WRITE_ONCE(nh_last_fw_status, status);
	if (!status)
		atomic64_inc(&nh_fw_ok);
	else
		atomic64_inc(&nh_fw_error);
	qdf_nbuf_free(packet);
	atomic_dec(&nh_inflight);
	module_put(THIS_MODULE);
	return QDF_STATUS_SUCCESS;
}

/* Use the existing host-managed station and its normal P2P ROC/management
 * lifecycle. The callee copies the frame before returning; no new firmware
 * vdev IDs, DMA buffers, or private completion descriptors are manufactured.
 * Success here means queued, never an independently confirmed RF result.
 */
static int nh_station_submit(struct hdd_context *hdd_ctx,
			     struct net_device *monitor,
			     struct ieee80211_channel *channel,
			     const void *frame, size_t length, bool dry_run,
			     const struct hdd_nh_tx_view *view)
{
	struct net_device *station;
	struct hdd_adapter *adapter;
	struct osif_vdev_sync *sync;
	struct wlan_objmgr_vdev *vdev;
	struct p2p_mgmt_tx params = {0};
	u64 cookie = 0;
	int result = -ENODEV;

	station = dev_get_by_name(dev_net(monitor), "wlan0");
	if (!station)
		return result;
	if (station == monitor || station->reg_state != NETREG_REGISTERED ||
	    !netif_running(station))
		goto put;
	adapter = WLAN_HDD_GET_PRIV_PTR(station);
	if (adapter->hdd_ctx != hdd_ctx || adapter->device_mode != QDF_STA_MODE)
		goto put;
	result = osif_vdev_sync_op_start(station, &sync);
	if (result)
		goto put;
	vdev = hdd_objmgr_get_vdev_by_user(adapter, WLAN_OSIF_P2P_ID);
	if (!vdev) {
		result = -ENODEV;
		goto stop;
	}
	result = qdf_status_to_os_return(ucfg_p2p_nh_station_peer_check(vdev));
	if (result)
		goto release;
	if (view->rate && hdd_nh_rate_index(view->rate) < 4 &&
	    channel->band != NL80211_BAND_2GHZ) {
		result = -EOPNOTSUPP;
		goto release;
	}
	if (dry_run) {
		result = 0;
	} else if (time_before(jiffies, nh_sta_next_tx)) {
		result = -EAGAIN;
	} else {
		/* Initial validation: bound scheduler pressure to ten frames/s. */
		nh_sta_next_tx = jiffies + msecs_to_jiffies(100);
		params.vdev_id = wlan_vdev_get_id(vdev);
		params.chan_freq = channel->center_freq;
		params.wait = 100;
		params.len = length;
		params.off_chan = true;
		params.dont_wait_for_ack = !!(view->tx_flags & 8) ||
			is_multicast_ether_addr((const uint8_t *)frame + 4);
		params.buf = frame;
		result = qdf_status_to_os_return(ucfg_p2p_mgmt_tx_nh(
			hdd_ctx->psoc, &params, &cookie, wlan_vdev_get_pdev(vdev),
			!!(view->tx_flags & 0x10), view->rate));
		if (!result)
			atomic64_inc(&nh_sta_queued);
	}
release:
	hdd_objmgr_put_vdev_by_user(vdev, WLAN_OSIF_P2P_ID);
stop:
	osif_vdev_sync_op_stop(sync);
put:
	dev_put(station);
	WRITE_ONCE(nh_sta_last_errno, result);
	return result;
}

static bool nh_process_packet(struct sk_buff *skb)
{
	struct net_device *dev = skb->dev;
	struct hdd_adapter *adapter = WLAN_HDD_GET_PRIV_PTR(dev);
	struct hdd_context *hdd_ctx;
	struct osif_vdev_sync *sync;
	struct wlan_objmgr_vdev *vdev = NULL;
	struct wlan_objmgr_peer *self_peer = NULL, *destination_peer;
	struct wlan_objmgr_pdev *pdev;
	struct ieee80211_channel *channel;
	struct wlan_channel *operating_channel;
	struct hdd_nh_tx_view view;
	void *packet = NULL, *data = NULL, *wma;
	QDF_STATUS status;
	bool submitted = false;
	bool dry_run = false;
	unsigned int mode = READ_ONCE(nh_tx_mode);
	unsigned int stage = 1;
	uint32_t frequency;

	if (!mode || READ_ONCE(nh_closing) ||
	    dev->reg_state != NETREG_REGISTERED || !netif_running(dev) ||
	    hdd_nh_parse_radiotap_ex(skb->data, skb->len,
				    hdd_nh_sta_backend_enabled() && nh_raw_frames, &view))
		goto reject;
	/* Metadata is supported only by the explicit station backend. */
	stage = 2;
	if (!hdd_nh_sta_backend_enabled() &&
	    (view.tx_flags || view.rate ||
	     cds_get_conparam() != QDF_GLOBAL_MONITOR_MODE))
		goto reject;
	stage = 3;
	if (osif_vdev_sync_op_start(dev, &sync))
		goto reject;
	hdd_ctx = WLAN_HDD_GET_CTX(adapter);
	stage = 4;
	if (wlan_hdd_validate_context(hdd_ctx) ||
	    adapter->device_mode != QDF_MONITOR_MODE ||
	    wlan_hdd_validate_vdev_id(adapter->vdev_id))
		goto stop;
	vdev = hdd_objmgr_get_vdev_by_user(adapter, WLAN_DP_ID);
	stage = 5;
	if (!vdev || QDF_IS_STATUS_ERROR(wlan_vdev_is_up_active_state(vdev)))
		goto release;
	/* Initial path uses the monitor vdev's self peer. Address spoofing and
	 * concurrent STA/monitor operation require a separately audited path.
	 */
	stage = 6;
	if (hdd_nh_validate_tx_request_backend(skb->data, skb->len, dev->dev_addr,
			 hdd_nh_sta_backend_enabled() && nh_random_sa,
			 hdd_nh_sta_backend_enabled() && nh_raw_frames, &view))
		goto release;
	if (hdd_nh_sta_backend_enabled()) {
		stage = 27;
		if (cds_get_conparam() != QDF_GLOBAL_MISSION_MODE ||
		    !ucfg_mlme_is_sta_mon_conc_supported(hdd_ctx->psoc) ||
		    READ_ONCE(adapter->monitor_mode_vdev_up_in_progress))
			goto release;
		operating_channel = wlan_vdev_mlme_get_bss_chan(vdev);
		if (!operating_channel)
			goto release;
		frequency = READ_ONCE(operating_channel->ch_freq);
		WRITE_ONCE(nh_last_freq, frequency);
		channel = ieee80211_get_channel(hdd_ctx->wiphy, frequency);
		if (!channel || channel->band == NL80211_BAND_6GHZ ||
		    channel->flags & (IEEE80211_CHAN_DISABLED | IEEE80211_CHAN_NO_IR |
				      IEEE80211_CHAN_RADAR))
			goto release;
		stage = 28;
		if (nh_station_submit(hdd_ctx, dev, channel,
				      skb->data + view.radiotap_len,
				      view.frame_len, mode == 1, &view))
			goto release;
		if (mode == 1)
			atomic64_inc(&nh_dry_run);
		/* The normal P2P stack owns its own copied frame, not our module
		 * reference. Release ours after the worker returns in either mode.
		 */
		dry_run = true;
		goto release;
	}
	pdev = wlan_vdev_get_pdev(vdev);
	stage = 7;
	if (!pdev)
		goto release;
	self_peer = wlan_objmgr_get_peer(hdd_ctx->psoc,
		wlan_objmgr_pdev_get_pdev_id(pdev), (void *)dev->dev_addr,
		WLAN_MGMT_NB_ID);
	stage = 8;
	if (!self_peer || wlan_peer_get_vdev(self_peer) != vdev)
		goto release;
	destination_peer = wlan_objmgr_get_peer(hdd_ctx->psoc,
		wlan_objmgr_pdev_get_pdev_id(pdev),
		skb->data + view.radiotap_len + 4, WLAN_MGMT_NB_ID);
	if (destination_peer) {
		bool same_vdev = wlan_peer_get_vdev(destination_peer) == vdev;

		wlan_objmgr_peer_release_ref(destination_peer, WLAN_MGMT_NB_ID);
		stage = 9;
		if (!same_vdev)
			goto release;
	}
	stage = 10;
	/* cfg80211's monitor-channel setter does not update mon_chan_freq.
	 * Use the UP vdev's operating channel, not that stale adapter cache.
	 */
	operating_channel = wlan_vdev_mlme_get_bss_chan(vdev);
	if (!operating_channel ||
	    READ_ONCE(adapter->monitor_mode_vdev_up_in_progress))
		goto release;
	frequency = READ_ONCE(operating_channel->ch_freq);
	WRITE_ONCE(nh_last_freq, frequency);
	channel = ieee80211_get_channel(hdd_ctx->wiphy, frequency);
	if (!channel || channel->band == NL80211_BAND_6GHZ ||
	    channel->flags & (IEEE80211_CHAN_DISABLED | IEEE80211_CHAN_NO_IR |
			      IEEE80211_CHAN_RADAR))
		goto release;
	if (mode == 1) {
		atomic64_inc(&nh_dry_run);
		dry_run = true;
		goto release;
	}
	wma = cds_get_context(QDF_MODULE_ID_WMA);
	stage = 11;
	if (!wma)
		goto release;
	stage = 12;
	if (atomic_inc_return(&nh_inflight) > NH_INFLIGHT_LIMIT) {
		atomic_dec(&nh_inflight);
		goto release;
	}
	status = cds_packet_alloc(view.frame_len, &data, &packet);
	stage = 13;
	if (QDF_IS_STATUS_ERROR(status)) {
		atomic_dec(&nh_inflight);
		goto release;
	}
	memcpy(data, skb->data + view.radiotap_len, view.frame_len);
	/* wma_tx_packet consumes packet on both submission success and failure.
	 * NULL download callback avoids its synchronous download wait. On
	 * success the queued module reference transfers to nh_ota_complete.
	 */
	status = wma_tx_packet(wma, packet, view.frame_len,
		TXRX_FRM_802_11_MGMT, ANI_TXDIR_TODS, 7, NULL, data,
		nh_ota_complete, 0, adapter->vdev_id, false,
		frequency, RATEID_DEFAULT, 0);
	stage = 14;
	if (QDF_IS_STATUS_SUCCESS(status)) {
		atomic64_inc(&nh_submitted);
		submitted = true;
	} else {
		atomic64_inc(&nh_submit_error);
		atomic_dec(&nh_inflight);
	}
release:
	if (self_peer)
		wlan_objmgr_peer_release_ref(self_peer, WLAN_MGMT_NB_ID);
	if (vdev)
		hdd_objmgr_put_vdev_by_user(vdev, WLAN_DP_ID);
stop:
	osif_vdev_sync_op_stop(sync);
	if (!submitted && !dry_run) {
		WRITE_ONCE(nh_last_reject, stage);
		atomic64_inc(&nh_rejected);
	}
	return submitted;
reject:
	WRITE_ONCE(nh_last_reject, stage);
	atomic64_inc(&nh_rejected);
	return false;
}

static void nh_tx_worker(struct work_struct *work)
{
	struct sk_buff *skb;
	bool submitted;
	unsigned int budget = NH_QUEUE_LIMIT;
	unsigned long flags;

	while (budget-- && (skb = skb_dequeue(&nh_queue))) {
		submitted = nh_process_packet(skb);
		dev_put(skb->dev);
		dev_kfree_skb_any(skb);
		if (!submitted)
			module_put(THIS_MODULE);
	}
	/* A continuous producer must not make the callback unbounded. The
	 * queue lock also serializes requeueing with driver shutdown.
	 */
	spin_lock_irqsave(&nh_queue.lock, flags);
	if (!nh_closing && nh_queue.qlen)
		schedule_work(&nh_work);
	spin_unlock_irqrestore(&nh_queue.lock, flags);
}

netdev_tx_t hdd_nh_monitor_xmit(struct sk_buff *skb, struct net_device *dev)
{
	unsigned long flags;

	if (!READ_ONCE(nh_tx_mode) || skb->len > 4096 ||
	    skb_linearize(skb) || !try_module_get(THIS_MODULE)) {
		WRITE_ONCE(nh_last_reject, 25);
		atomic64_inc(&nh_rejected);
		dev_kfree_skb_any(skb);
		return NETDEV_TX_OK;
	}
	spin_lock_irqsave(&nh_queue.lock, flags);
	if (nh_closing || nh_queue.qlen >= NH_QUEUE_LIMIT) {
		spin_unlock_irqrestore(&nh_queue.lock, flags);
		WRITE_ONCE(nh_last_reject, 26);
		atomic64_inc(&nh_rejected);
		dev_kfree_skb_any(skb);
		module_put(THIS_MODULE);
		return NETDEV_TX_OK;
	}
	skb->dev = dev;
	dev_hold(dev);
	__skb_queue_tail(&nh_queue, skb);
	schedule_work(&nh_work);
	spin_unlock_irqrestore(&nh_queue.lock, flags);
	return NETDEV_TX_OK;
}

void hdd_nh_tx_resume(void)
{
	WRITE_ONCE(nh_closing, false);
}

void hdd_nh_tx_shutdown(void)
{
	unsigned long flags;
	struct sk_buff *skb;

	spin_lock_irqsave(&nh_queue.lock, flags);
	nh_closing = true;
	spin_unlock_irqrestore(&nh_queue.lock, flags);
	cancel_work_sync(&nh_work);
	while ((skb = skb_dequeue(&nh_queue))) {
		dev_put(skb->dev);
		dev_kfree_skb_any(skb);
		module_put(THIS_MODULE);
	}
}

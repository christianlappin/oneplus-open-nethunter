/* SPDX-License-Identifier: GPL-2.0-only */
/* Read-only legacy queries used by unmodified Aircrack-ng's Linux backend. */
#include <net/iw_handler.h>
#include "wlan_hdd_includes.h"
#include "wlan_hdd_main.h"
#include "wlan_hdd_object_manager.h"
#include "wlan_hdd_nh_tx.h"
#include "wlan_vdev_mlme_api.h"
#include "osif_vdev_sync.h"

static int nh_iw_name(struct net_device *dev, struct iw_request_info *info,
		      union iwreq_data *data, char *extra)
{
	strscpy(data->name, "IEEE 802.11", IFNAMSIZ);
	return 0;
}

static int nh_iw_mode(struct net_device *dev, struct iw_request_info *info,
		      union iwreq_data *data, char *extra)
{
	data->mode = IW_MODE_MONITOR;
	return 0;
}

static int nh_iw_frequency(struct net_device *dev, struct iw_request_info *info,
			   union iwreq_data *data, char *extra)
{
	struct hdd_adapter *adapter = WLAN_HDD_GET_PRIV_PTR(dev);
	struct wlan_objmgr_vdev *vdev;
	struct wlan_channel *channel;
	struct osif_vdev_sync *sync;
	int result;
	unsigned int frequency;

	result = osif_vdev_sync_op_start(dev, &sync);
	if (result)
		return result;
	result = -ENODEV;
	vdev = hdd_objmgr_get_vdev_by_user(adapter, WLAN_DP_ID);
	if (!vdev)
		goto stop;
	channel = wlan_vdev_mlme_get_bss_chan(vdev);
	if (!channel || READ_ONCE(adapter->monitor_mode_vdev_up_in_progress))
		goto release;
	frequency = READ_ONCE(channel->ch_freq);
	if (!frequency)
		goto release;
	data->freq.m = frequency;
	data->freq.e = 6;
	data->freq.i = ieee80211_frequency_to_channel(frequency);
	data->freq.flags = IW_FREQ_FIXED;
	result = 0;
release:
	hdd_objmgr_put_vdev_by_user(vdev, WLAN_DP_ID);
stop:
	osif_vdev_sync_op_stop(sync);
	return result;
}

static const iw_handler nh_iw_handlers[] = {
	[SIOCGIWNAME - SIOCIWFIRST] = nh_iw_name,
	[SIOCGIWMODE - SIOCIWFIRST] = nh_iw_mode,
	[SIOCGIWFREQ - SIOCIWFIRST] = nh_iw_frequency,
};

static const struct iw_handler_def nh_iw_definition = {
	.num_standard = ARRAY_SIZE(nh_iw_handlers),
	.standard = nh_iw_handlers,
};

void hdd_nh_wext_attach(struct net_device *dev)
{
	if (hdd_nh_sta_backend_enabled())
		dev->wireless_handlers = &nh_iw_definition;
}

/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _WLAN_HDD_NH_TX_H
#define _WLAN_HDD_NH_TX_H
#include <linux/netdevice.h>
#include <linux/skbuff.h>
netdev_tx_t hdd_nh_monitor_xmit(struct sk_buff *skb, struct net_device *dev);
void hdd_nh_tx_resume(void);
void hdd_nh_tx_shutdown(void);
bool hdd_nh_sta_backend_enabled(void);
int hdd_nh_set_monitor_frequency(unsigned int frequency);
int hdd_nh_stop_monitor(struct net_device *dev);
void hdd_nh_monitor_stop_ack(unsigned int vdev_id);
void hdd_nh_wext_attach(struct net_device *dev);
int hdd_nh_get_monitor_rx_state(char *buffer);
int hdd_nh_dp_rx_state(void *handle, char *buffer);
int hdd_nh_refresh_monitor_rx(void);
int hdd_nh_dp_refresh_monitor_rx(void *handle);
#endif

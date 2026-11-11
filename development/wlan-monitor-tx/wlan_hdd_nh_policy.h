/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _WLAN_HDD_NH_POLICY_H
#define _WLAN_HDD_NH_POLICY_H
#include "wlan_hdd_nh_radiotap.h"

/* Shared with the host tests: the initial backend supports the self-peer MAC,
 * management frames on the current channel, and standard ACK semantics.
 */
static inline int
hdd_nh_validate_tx_request_backend(const unsigned char *packet, size_t len,
			   const unsigned char self[6],
			   int allow_foreign_source, int allow_raw,
			   struct hdd_nh_tx_view *view)
{
	struct hdd_nh_tx_view parsed;
	int result;
	unsigned int i;
	unsigned char nonzero = 0;

	if (!view || !self)
		return -EINVAL;
	view->radiotap_len = 0;
	view->frame_len = 0;
	view->tx_flags = 0;
	view->rate = 0;
	if (len > 4096)
		return -EMSGSIZE;
	result = hdd_nh_parse_radiotap_ex(packet, len, allow_raw, &parsed);
	if (result)
		return result;
	if (!(packet[parsed.radiotap_len] & 0x0c) &&
	    (packet[parsed.radiotap_len + 1] & 0x03))
		return -EOPNOTSUPP;
	if (packet[parsed.radiotap_len + 10] & 1)
		return -EADDRNOTAVAIL;
	for (i = 0; i < 6; i++) {
		nonzero |= packet[parsed.radiotap_len + 10 + i];
		if (!allow_foreign_source &&
		    packet[parsed.radiotap_len + 10 + i] != self[i])
			return -EADDRNOTAVAIL;
	}
	if (!nonzero)
		return -EADDRNOTAVAIL;
	*view = parsed;
	return 0;
}

static inline int
hdd_nh_validate_tx_request_ex(const unsigned char *packet, size_t len,
			   const unsigned char self[6], int allow_foreign_source,
			   struct hdd_nh_tx_view *view)
{
	return hdd_nh_validate_tx_request_backend(packet, len, self,
						 allow_foreign_source, 0, view);
}

static inline int
hdd_nh_validate_tx_request(const unsigned char *packet, size_t len,
			   const unsigned char self[6],
			   struct hdd_nh_tx_view *view)
{
	return hdd_nh_validate_tx_request_ex(packet, len, self, 0, view);
}
#endif

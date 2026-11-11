/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _WLAN_HDD_NH_RADIOTAP_H
#define _WLAN_HDD_NH_RADIOTAP_H

#ifdef __KERNEL__
#include <linux/types.h>
#include <linux/errno.h>
#else
#include <stddef.h>
#include <errno.h>
#endif

/* Initial management-TX subset: current channel, firmware-selected rate.
 * Reject unsupported radiotap requests rather than silently ignoring them.
 * This parser alone does not register a TX callback or transmit any frame.
 */
struct hdd_nh_tx_view {
	size_t radiotap_len;
	size_t frame_len;
	unsigned short tx_flags;
	unsigned char rate; /* Radiotap units of 500 kbit/s; zero means automatic. */
};

static inline int hdd_nh_rate_index(unsigned char rate)
{
	static const unsigned char rates[] = {2, 4, 11, 22, 12, 18, 24, 36,
					    48, 72, 96, 108};
	unsigned int i;

	for (i = 0; i < sizeof(rates); i++)
		if (rates[i] == rate)
			return i;
	return -EOPNOTSUPP;
}

static inline unsigned short hdd_nh_get_le16(const unsigned char *p)
{
	return p[0] | ((unsigned short)p[1] << 8);
}

static inline int
hdd_nh_parse_radiotap_ex(const unsigned char *packet, size_t len,
		      int allow_raw,
		      struct hdd_nh_tx_view *view)
{
	unsigned int present;
	unsigned short header_len, tx_flags = 0;
	unsigned char flags = 0, rate = 0;
	size_t offset = 8, frame_len;
	const unsigned char *frame;
	/* Fixed body lengths required before existing driver routines may
	 * inspect an auth algorithm, reason code, or action category/code.
	 * 255 marks subtypes outside the initial implementation's scope.
	 */
	static const unsigned char min_body[16] = {
		4, 6, 10, 6, 0, 12, 255, 255,
		12, 0, 2, 6, 2, 2, 2, 255
	};
	unsigned char subtype;

	if (!view)
		return -EINVAL;
	view->radiotap_len = 0;
	view->frame_len = 0;
	view->tx_flags = 0;
	view->rate = 0;
	if (!packet || len < 8)
		return -EMSGSIZE;
	if (packet[0] != 0)
		return -EOPNOTSUPP;
	header_len = hdd_nh_get_le16(packet + 2);
	if (header_len < 8 || header_len > len)
		return -EMSGSIZE;
	present = packet[4] | ((unsigned int)packet[5] << 8) |
		  ((unsigned int)packet[6] << 16) |
		  ((unsigned int)packet[7] << 24);
	/* FLAGS, legacy RATE, TX_FLAGS. Channel overrides, MCS, VHT and
	 * extension/vendor namespaces require a separate backend.
	 */
	if (present & ~((1U << 1) | (1U << 2) | (1U << 15)))
		return -EOPNOTSUPP;
	if (present & (1U << 1)) {
		if (offset >= header_len)
			return -EMSGSIZE;
		flags = packet[offset++];
	}
	if (present & (1U << 2)) {
		if (offset >= header_len)
			return -EMSGSIZE;
		rate = packet[offset++];
		if (rate && hdd_nh_rate_index(rate) < 0)
			return -EOPNOTSUPP;
	}
	if (present & (1U << 15)) {
		offset = (offset + 1) & ~(size_t)1;
		if (offset + 2 > header_len)
			return -EMSGSIZE;
		tx_flags = hdd_nh_get_le16(packet + offset);
		/* NOACK and NOSEQ are handled explicitly by the STA backend. */
		if (tx_flags & ~0x0018U)
			return -EOPNOTSUPP;
	}
	if (flags & 0x40) /* BADFCS */
		return -EINVAL;
	if (flags & ~0x10U) /* Only the included-FCS indication is supported. */
		return -EOPNOTSUPP;
	frame_len = len - header_len;
	if (flags & 0x10) {
		if (frame_len < 4)
			return -EMSGSIZE;
		frame_len -= 4;
	}
	if (frame_len < 2 || frame_len > 2304)
		return -EMSGSIZE;
	frame = packet + header_len;
	if (frame[0] & 3)
		return -EOPNOTSUPP;
	subtype = frame[0] >> 4;
	switch (frame[0] & 0x0c) {
	case 0:
		if (min_body[subtype] == 255)
			return -EOPNOTSUPP;
		if (frame_len < 24 + (size_t)min_body[subtype])
			return -EMSGSIZE;
		if ((frame[1] & 0x44) || (frame[22] & 0x0f))
			return -EOPNOTSUPP;
		break;
	case 4:
		/* RTS has both receiver and transmitter addresses. */
		if (!allow_raw || subtype != 11 || (frame[1] & 0x47))
			return -EOPNOTSUPP;
		if (frame_len != 16)
			return -EMSGSIZE;
		break;
	case 8: {
		size_t mac_len = 24;

		if (!allow_raw || subtype == 13)
			return -EOPNOTSUPP;
		if ((frame[1] & 3) == 3)
			mac_len += 6;
		if (subtype & 8) {
			mac_len += 2;
			if (frame[1] & 0x80)
				mac_len += 4;
		}
		if (frame_len < mac_len)
			return -EMSGSIZE;
		break;
	}
	default:
		return -EOPNOTSUPP;
	}
	view->radiotap_len = header_len;
	view->frame_len = frame_len;
	view->tx_flags = tx_flags;
	view->rate = rate;
	return 0;
}

static inline int
hdd_nh_parse_radiotap(const unsigned char *packet, size_t len,
		      struct hdd_nh_tx_view *view)
{
	return hdd_nh_parse_radiotap_ex(packet, len, 0, view);
}
#endif

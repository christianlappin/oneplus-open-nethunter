#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wlan_hdd_nh_radiotap.h"

static unsigned char packet[4096];
static struct hdd_nh_tx_view view;

static void base(unsigned char fields, unsigned short header)
{
    memset(packet, 0, sizeof(packet));
    packet[2] = header;
    packet[3] = header >> 8;
    packet[4] = fields;
    packet[header] = 0x40; /* Probe request header; never transmitted. */
}

int main(void)
{
    base(0, 8);
    assert(!hdd_nh_parse_radiotap(packet, 32, &view));
    assert(view.radiotap_len == 8 && view.frame_len == 24);
    for (size_t n = 0; n < 32; n++)
        assert(hdd_nh_parse_radiotap(packet, n, &view));
    base(2, 12); packet[5] = 0x80; packet[8] = 0x10; packet[10] = 8;
    assert(!hdd_nh_parse_radiotap(packet, 40, &view));
    assert(view.frame_len == 24 && view.tx_flags == 8);
    packet[2] = 11;
    assert(hdd_nh_parse_radiotap(packet, 40, &view) == -EMSGSIZE);
    base(2, 9); packet[8] = 0x40;
    assert(hdd_nh_parse_radiotap(packet, 33, &view) == -EINVAL);
    base(4, 9); packet[8] = 3; /* Invalid legacy rate. */
    assert(hdd_nh_parse_radiotap(packet, 33, &view) == -EOPNOTSUPP);
    /* Exact transmit envelope from Aircrack-ng 4bf83f1a linux_write(). */
    const unsigned char aircrack_rtap[] = {0,0,12,0,4,128,0,0,2,0,24,0};
    base(0, 12); memcpy(packet, aircrack_rtap, sizeof(aircrack_rtap));
    assert(!hdd_nh_parse_radiotap(packet, 36, &view));
    assert(view.rate == 2 && view.tx_flags == 0x18 && view.radiotap_len == 12);
    for (size_t n = 0; n < 36; n++)
        assert(hdd_nh_parse_radiotap(packet, n, &view));
    for (unsigned int code = 1; code < 256; code++) {
        base(4, 9); packet[8] = code;
        int index = hdd_nh_rate_index(code);
        assert((hdd_nh_parse_radiotap(packet, 33, &view) == 0) == (index >= 0));
        if (index >= 0) assert(index < 12 && view.rate == code);
    }
    base(0, 8); packet[7] = 0x80; /* Extended bitmap. */
    assert(hdd_nh_parse_radiotap(packet, 32, &view) == -EOPNOTSUPP);
    base(0, 8); packet[8] = 0x08; /* Data frame. */
    assert(hdd_nh_parse_radiotap(packet, 32, &view) == -EOPNOTSUPP);
    base(0, 8); packet[9] = 0x40; /* Protected frame. */
    assert(hdd_nh_parse_radiotap(packet, 32, &view) == -EOPNOTSUPP);
    base(0, 8); packet[30] = 1; /* Nonzero fragment number. */
    assert(hdd_nh_parse_radiotap(packet, 32, &view) == -EOPNOTSUPP);
    base(0, 8);
    assert(hdd_nh_parse_radiotap(packet, 2400, &view) == -EMSGSIZE);
    assert(hdd_nh_parse_radiotap(NULL, 0, &view) == -EMSGSIZE);
    assert(hdd_nh_parse_radiotap(packet, 32, NULL) == -EINVAL);
    base(0, 8); packet[8] = 0xb0; /* Auth needs a six-byte fixed body. */
    assert(hdd_nh_parse_radiotap(packet, 37, &view) == -EMSGSIZE);
    assert(!hdd_nh_parse_radiotap(packet, 38, &view));
    base(0, 8); packet[8] = 0x80; /* Beacon needs twelve fixed bytes. */
    assert(hdd_nh_parse_radiotap(packet, 43, &view) == -EMSGSIZE);
    assert(!hdd_nh_parse_radiotap(packet, 44, &view));
    base(0, 8); packet[8] = 0xf0;
    assert(hdd_nh_parse_radiotap(packet, 32, &view) == -EOPNOTSUPP);
    uint32_t rng = 0x12345678;
    for (int test = 0; test < 100000; test++) {
        size_t n = (rng >> 8) % 512;
        unsigned char *p = malloc(n ? n : 1);
        assert(p);
        for (size_t i = 0; i < n; i++) {
            rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
            p[i] = rng;
        }
        int result = hdd_nh_parse_radiotap(p, n, &view);
        if (!result) {
            assert(view.radiotap_len <= n && view.frame_len >= 24);
            assert(view.frame_len <= n - view.radiotap_len);
        } else {
            assert(!view.radiotap_len && !view.frame_len && !view.tx_flags);
        }
        free(p);
        rng = rng * 1664525U + 1013904223U;
    }
    puts("PASS: radiotap boundary/unsupported-feature tests and 100000 fuzz inputs");
    return 0;
}

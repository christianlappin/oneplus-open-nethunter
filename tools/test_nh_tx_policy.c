#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wlan_hdd_nh_policy.h"

static const unsigned char self[6] = { 2, 1, 2, 3, 4, 5 };
static unsigned char packet[4097];
static struct hdd_nh_tx_view view;

static void probe(unsigned short header)
{
    memset(packet, 0, sizeof(packet));
    packet[2] = header;
    packet[header] = 0x40;
    memcpy(packet + header + 10, self, sizeof(self));
}

int main(void)
{
    probe(8);
    assert(!hdd_nh_validate_tx_request(packet, 32, self, &view));
    for (size_t n = 0; n < 32; n++)
        assert(hdd_nh_validate_tx_request(packet, n, self, &view));
    packet[18] ^= 1;
    assert(hdd_nh_validate_tx_request(packet, 32, self, &view) == -EADDRNOTAVAIL);
    assert(!view.frame_len);
    probe(8); packet[18] = 0; /* aireplay uses globally administered random SAs. */
    assert(hdd_nh_validate_tx_request(packet, 32, self, &view) == -EADDRNOTAVAIL);
    assert(!hdd_nh_validate_tx_request_ex(packet, 32, self, 1, &view));
    packet[18] = 1;
    assert(hdd_nh_validate_tx_request_ex(packet, 32, self, 1, &view) == -EADDRNOTAVAIL);
    memset(packet + 18, 0, 6);
    assert(hdd_nh_validate_tx_request_ex(packet, 32, self, 1, &view) == -EADDRNOTAVAIL);
    probe(10); packet[5] = 0x80; packet[8] = 8;
    assert(!hdd_nh_validate_tx_request(packet, 34, self, &view));
    assert(view.tx_flags == 8);
    packet[8] = 4;
    assert(hdd_nh_validate_tx_request(packet, 34, self, &view) == -EOPNOTSUPP);
    probe(8); packet[9] = 1;
    assert(hdd_nh_validate_tx_request(packet, 32, self, &view) == -EOPNOTSUPP);
    probe(8); packet[8] = 0xb0;
    assert(hdd_nh_validate_tx_request(packet, 37, self, &view) == -EMSGSIZE);
    assert(!hdd_nh_validate_tx_request(packet, 38, self, &view));
    assert(hdd_nh_validate_tx_request(packet, sizeof(packet), self, &view) == -EMSGSIZE);
    assert(hdd_nh_validate_tx_request(packet, 38, NULL, &view) == -EINVAL);
    assert(hdd_nh_validate_tx_request(packet, 38, self, NULL) == -EINVAL);
    /* Exercise valid radiotap envelopes with all management subtypes/body
     * truncations, unlike wholly random fuzzing which usually fails at byte0.
     */
    for (unsigned int subtype = 0; subtype < 16; subtype++) {
        for (size_t length = 0; length < 128; length++) {
            unsigned char *p = calloc(length ? length : 1, 1);
            assert(p);
            if (length >= 8) p[2] = 8;
            if (length >= 9) p[8] = subtype << 4;
            if (length >= 24) memcpy(p + 18, self, sizeof(self));
            int result = hdd_nh_validate_tx_request(p, length, self, &view);
            if (!result) {
                assert(view.frame_len >= 24);
                assert(view.radiotap_len + view.frame_len <= length);
            } else {
                assert(!view.frame_len);
            }
            free(p);
        }
    }
    puts("PASS: TX admission policy and 2048 subtype/truncation inputs");
    return 0;
}

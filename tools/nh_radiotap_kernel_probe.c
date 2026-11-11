#include <linux/module.h>
#include "wlan_hdd_nh_radiotap.h"
int nh_parser_probe(const unsigned char *packet, size_t len,
                    struct hdd_nh_tx_view *view);
int __used nh_parser_probe(const unsigned char *packet, size_t len,
                          struct hdd_nh_tx_view *view)
{
    return hdd_nh_parse_radiotap(packet, len, view);
}
MODULE_LICENSE("GPL");

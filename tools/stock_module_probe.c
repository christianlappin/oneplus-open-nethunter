#include <linux/module.h>
#include <linux/netdevice.h>
static int __init probe_init(void) { return 0; }
static void __exit probe_exit(void) { }
module_init(probe_init);
module_exit(probe_exit);
MODULE_LICENSE("GPL");

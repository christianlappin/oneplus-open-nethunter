#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <poll.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <bluetooth/bluetooth.h>
#include <bluetooth/hci.h>
#include <bluetooth/hci_lib.h>

/* Local commands only: no discovery, advertising, pairing, or connections. */
static int read_version_user_channel(void)
{
    struct sockaddr_hci address = {
        .hci_family = AF_BLUETOOTH, .hci_dev = 0,
        .hci_channel = HCI_CHANNEL_USER
    };
    const unsigned char command[] = { HCI_COMMAND_PKT, 0x01, 0x10, 0x00 };
    unsigned char reply[260];
    int fd = socket(AF_BLUETOOTH, SOCK_RAW | SOCK_CLOEXEC, BTPROTO_HCI);
    if (fd < 0) return 1;
    if (bind(fd, (struct sockaddr *)&address, sizeof(address))) {
        fprintf(stderr, "HCI user channel bind: errno=%d (%s)\n", errno, strerror(errno));
        close(fd); return 1;
    }
    if (write(fd, command, sizeof(command)) != sizeof(command)) {
        perror("HCI user command write"); close(fd); return 1;
    }
    /* Bounded event consumption: only accept this command's completion. */
    for (int i = 0; i < 8; i++) {
        struct pollfd p = { .fd = fd, .events = POLLIN };
        if (poll(&p, 1, 250) <= 0) continue;
        ssize_t n = read(fd, reply, sizeof(reply));
        if (n >= 15 && reply[0] == HCI_EVENT_PKT && reply[1] == EVT_CMD_COMPLETE &&
            reply[4] == 0x01 && reply[5] == 0x10 && reply[6] == 0) {
            printf("HCI user channel local version reply: manufacturer=%u "
                   "hci_version=%u lmp_version=%u\n",
                   reply[11] | (reply[12] << 8), reply[7], reply[10]);
            close(fd); return 0;
        }
    }
    fputs("No valid local-version reply on HCI user channel\n", stderr);
    close(fd); return 1;
}

int main(void)
{
    int control = socket(AF_BLUETOOTH, SOCK_RAW | SOCK_CLOEXEC, BTPROTO_HCI);
    int fd = -1, raised = 0, result = 1;
    struct hci_dev_info info = { .dev_id = 0 };
    struct hci_version version;
    if (control < 0) { perror("HCI socket"); return 1; }
    if (ioctl(control, HCIGETDEVINFO, &info)) {
        perror("HCIGETDEVINFO"); goto done;
    }
    printf("hci0 registered; nonzero controller address=%s flags=0x%lx\n",
           bacmp(&info.bdaddr, BDADDR_ANY) ? "yes" : "no", (unsigned long)info.flags);
    if (!(info.flags & (1UL << HCI_UP))) {
        errno = 0;
        int up = ioctl(control, HCIDEVUP, 0);
        fprintf(stderr, "HCIDEVUP result=%d errno=%d (%s)\n", up, errno, strerror(errno));
        if (up < 0 || ioctl(control, HCIGETDEVINFO, &info) < 0 ||
            !(info.flags & (1UL << HCI_UP))) {
            result = read_version_user_channel();
            goto done;
        }
        raised = 1;
    }
    fd = hci_open_dev(0);
    if (fd < 0 || hci_read_local_version(fd, &version, 2000)) {
        perror("HCI Read Local Version"); goto done;
    }
    printf("Local controller replied: manufacturer=%u hci_version=%u "
           "hci_revision=%u lmp_version=%u lmp_subversion=%u\n",
           version.manufacturer, version.hci_ver, version.hci_rev,
           version.lmp_ver, version.lmp_subver);
    puts("PASS: native HCI local controller access; no discovery or pairing requested");
    result = 0;
done:
    if (fd >= 0) hci_close_dev(fd);
    if (raised && ioctl(control, HCIDEVDOWN, 0)) {
        perror("HCIDEVDOWN"); result = 1;
    }
    close(control);
    return result;
}

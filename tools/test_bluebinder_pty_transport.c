#include "hci_pty.h"
#include <stdio.h>
#include <unistd.h>

int main(void)
{
    int slave = -1;
    /* Exact bridge transport helper, with no HAL or physical radio.
     * RAW suppresses controller initialization. */
    int master = bluebinder_open_hci_pty(&slave, 1);
    if (master < 0) { perror("open synthetic HCI PTY"); return 1; }
    sleep(1);
    bluebinder_close_hci_pty(&slave);
    close(master);
    if (slave != -1) return 2;
    puts("PASS: bridge transport registered and closed synthetic HCI device");
    return 0;
}

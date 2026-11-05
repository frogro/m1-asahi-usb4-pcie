#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/loop.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>
#ifndef EXPECTED_RELEASE
#define EXPECTED_RELEASE "7.2.12-googlebook-usb4-egpu1"
#endif
static void fail(const char *s) {
    dprintf(2, "GOOGLEBOOK_INIT: %s: %s\n", s, strerror(errno));
    sync();
    /* Preserve diagnostics; do not create an unattended reboot loop. */
    for (;;) pause();
}
static void mkdir_ok(const char *p) {
    if (mkdir(p, 0755) && errno != EEXIST) fail(p);
}
static void node(const char *p, mode_t mode, unsigned major_n, unsigned minor_n) {
    if (mknod(p, mode, makedev(major_n, minor_n)) && errno != EEXIST) fail(p);
}
static void stdio_init(void) {
    int fd = open("/dev/console", O_RDWR | O_NOCTTY);
    if (fd < 0) fail("open console");
    for (int i = 0; i < 3; i++) if (dup2(fd, i) < 0) fail("console duplication");
    if (fd > 2) close(fd);
    setbuf(stdout, NULL);
}
static void write_all(int fd, const void *buf, size_t len) {
    const char *p = buf;
    while (len) {
        ssize_t n = write(fd, p, len);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) fail("write");
        p += n; len -= (size_t)n;
    }
}
static void write_text(const char *path, const char *text) {
    int fd = open(path, O_WRONLY | O_TRUNC | O_CLOEXEC);
    if (fd < 0) fail(path);
    write_all(fd, text, strlen(text));
    if (close(fd)) fail("close written file");
}
/* The loop driver retains the backing inode after Android frees the ramdisk.
 * Both loop devices are read-only, without AUTOCLEAR, until shutdown. */
static void attach_image(const char *image, char path[64]) {
    int ctl = open("/dev/loop-control", O_RDWR | O_CLOEXEC);
    if (ctl < 0) fail("loop-control");
    int n = ioctl(ctl, LOOP_CTL_GET_FREE);
    if (n < 0) fail("allocate loop");
    close(ctl);
    snprintf(path, 64, "/dev/block/loop%d", n);
    node(path, S_IFBLK | 0600, 7, (unsigned)n);
    int backing = open(image, O_RDONLY | O_CLOEXEC);
    int loop = open(path, O_RDONLY | O_CLOEXEC);
    if (backing < 0 || loop < 0) fail("open module image/loop");
    struct loop_config config = {0};
    config.fd = backing;
    config.info.lo_flags = LO_FLAGS_READ_ONLY;
    if (ioctl(loop, LOOP_CONFIGURE, &config)) fail("configure module image");
    close(loop); close(backing);
    printf("GOOGLEBOOK_INIT: %s attached read-only at %s\n", image, path);
}
static void bind_fstab_devices(const char *path, const char *vendor, const char *system) {
    FILE *f = fopen(path, "re");
    if (!f) fail(path);
    char *buf = NULL; size_t cap = 0; ssize_t len;
    char output[32768]; size_t used = 0; unsigned nv = 0, ns = 0;
    while ((len = getline(&buf, &cap, f)) >= 0) {
        const char *line = buf;
        char replacement[256];
        if (!strncmp(buf, "GBOOK_VENDOR_LOOP ", 18)) {
            snprintf(replacement, sizeof(replacement), "# %s /vendor_dlkm mounted read-only by bootstrap\n", vendor);
            line = replacement; nv++;
        } else if (!strncmp(buf, "GBOOK_SYSTEM_LOOP ", 18)) {
            snprintf(replacement, sizeof(replacement), "# %s /system_dlkm mounted read-only by bootstrap\n", system);
            line = replacement; ns++;
        }
        size_t size = strlen(line);
        if (used + size >= sizeof(output)) { errno = EFBIG; fail("fstab size"); }
        memcpy(output + used, line, size); used += size;
    }
    if (ferror(f) || nv != 1 || ns != 1) { errno = EINVAL; fail("fstab module entries"); }
    fclose(f); free(buf); output[used] = 0; write_text(path, output);
}
#include "profile.h"
static void load_module(const char *path, int optional) {
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) fail(path);
    const char *args = strstr(path, "/thunderbolt/thunderbolt.ko") ?
        "boot_protect_uuid=" SELECTED_ROUTER : "";
    int rc = syscall(SYS_finit_module, fd, args, 0), saved = errno;
    close(fd);
    if (rc && saved != EEXIST) {
        errno = saved;
        if (!optional) fail(path);
        dprintf(2, "GOOGLEBOOK_INIT: optional %s: %s\n", path, strerror(saved));
    }
}

#include "root-access.h"
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--self-test")) {
        puts("Googlebook bootstrap " EXPECTED_RELEASE); return 0;
    }
    int test = argc == 2 && !strcmp(argv[1], "--loop-self-test");
    if (getpid() != 1) { fprintf(stderr, "PID 1 required\n"); return 2; }
    mkdir_ok("/dev");
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, NULL)) fail("devtmpfs");
    node("/dev/console", S_IFCHR | 0600, 5, 1);
    node("/dev/null", S_IFCHR | 0666, 1, 3);
    node("/dev/loop-control", S_IFCHR | 0600, 10, 237);
    stdio_init(); mkdir_ok("/dev/block"); mkdir_ok("/proc"); mkdir_ok("/sys");
    if (mount("proc", "/proc", "proc", 0, NULL) || mount("sysfs", "/sys", "sysfs", 0, NULL)) fail("proc/sys");
    struct utsname u;
    if (uname(&u)) fail("uname");
    if (!test && strcmp(u.release, EXPECTED_RELEASE)) { errno = EINVAL; fail("kernel/module release mismatch"); }
    char vendor[64], system[64];
    attach_image("/googlebook-vendor_dlkm.erofs", vendor);
    attach_image("/googlebook-system_dlkm.erofs", system);
    bind_fstab_devices("/first_stage_ramdisk/fstab.android-desktop", vendor, system);
    mkdir_ok("/m1-modulefs");
    if (test && access("/test-erofs.ko", R_OK) == 0) load_module("/test-erofs.ko", 0);
    if (mount(vendor, "/m1-modulefs", "erofs", MS_RDONLY, NULL)) fail("module filesystem");
    if (test) {
        /* Simulate cleanup of the old ramdisk, then mount again from retained loops. */
        if (unlink("/googlebook-vendor_dlkm.erofs") || unlink("/googlebook-system_dlkm.erofs")) fail("test unlink");
        if (umount("/m1-modulefs") || mount(vendor, "/m1-modulefs", "erofs", MS_RDONLY, NULL)) fail("test remount");
        int fd = open("/m1-modulefs/marker", O_RDONLY); char b[32] = {0};
        if (fd < 0 || read(fd, b, sizeof(b)-1) < 0 || strcmp(b, "loop-retention-ok\n")) { errno = EIO; fail("test marker"); }
        close(fd);
        if (umount("/m1-modulefs") || mount(system, "/m1-modulefs", "erofs", MS_RDONLY, NULL)) fail("test system module image");
        puts("GOOGLEBOOK_LOOP_TEST_PASS"); sync(); reboot(RB_POWER_OFF); return 0;
    }
    write_text("/sys/module/firmware_class/parameters/path", "/m1-modulefs/lib/modules/firmware");
#include "preload.inc"
    wait_selected_root();
    write_text("/sys/module/firmware_class/parameters/path", "/vendor/lib/modules/firmware");
    if (umount("/m1-modulefs")) fail("unmount preload image");
    /* Android's strict boot-device check rejects virtual loop devices as
     * physical boot partitions. Mount them here instead; Android SwitchRoot
     * moves these mounts through both root transitions. Keep disk identity
     * checks and SELinux enforcing unchanged. */
    mkdir_ok("/vendor_dlkm"); mkdir_ok("/system_dlkm");
    if (mount(vendor, "/vendor_dlkm", "erofs", MS_RDONLY, NULL) ||
        mount(system, "/system_dlkm", "erofs", MS_RDONLY, NULL)) fail("mount retained module images");
    puts("GOOGLEBOOK_INIT: starting Android with pre-mounted matching module images");
    if (umount2("/sys", MNT_DETACH) || umount2("/proc", MNT_DETACH) || umount2("/dev", MNT_DETACH)) fail("detach bootstrap mounts");
    execl("/init", "/init", NULL); fail("exec Android init"); return 1;
}

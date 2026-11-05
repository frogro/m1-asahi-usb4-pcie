/* Early access to the selected external Android disk. No wildcard authorization. */
#include <glob.h>
#include <limits.h>
#include <time.h>
static int small_read(const char *path, char *buf, size_t cap) {
    int fd=open(path,O_RDONLY|O_CLOEXEC); if(fd<0)return 0;
    ssize_t n=read(fd,buf,cap-1);close(fd);if(n<0)return 0;
    buf[n]=0;buf[strcspn(buf,"\r\n")]=0;return 1;
}
static int selected_super_present(void) {
    glob_t g={0};int found=0;
    if(glob("/sys/class/block/*/uevent",0,NULL,&g)==0) {
        for(size_t i=0;i<g.gl_pathc;i++) {
            FILE *f=fopen(g.gl_pathv[i],"re");if(!f)continue;
            char line[256];while(fgets(line,sizeof(line),f)) {
                line[strcspn(line,"\r\n")]=0;
                if(!strcmp(line,"PARTUUID=" SELECTED_SUPER))found++;
            }fclose(f);
        }
    }globfree(&g);return found==1;
}
static int id_is(const char *node,const char *id) {
    char path[PATH_MAX],buf[128];
    if(snprintf(path,sizeof(path),"%s/unique_id",node)>=(int)sizeof(path))return 0;
    return small_read(path,buf,sizeof(buf))&&!strcmp(buf,id);
}
static int host_node(const char *node) {
    const char *base=strrchr(node,'/');if(!base)return 0;
    unsigned d;
    if(sscanf(base+1,"%u",&d)!=1)return 0;
    char hn[32];snprintf(hn,sizeof(hn),"%u-0",d);if(strcmp(base+1,hn))return 0;
    char parent[PATH_MAX];snprintf(parent,sizeof(parent),"%s",node);
    *strrchr(parent,'/')=0;char expected[32];snprintf(expected,sizeof(expected),"domain%u",d);
    const char *pb=strrchr(parent,'/');if(!pb||strcmp(pb+1,expected))return 0;
    char path[PATH_MAX],buf[32];
    if(snprintf(path,sizeof(path),"%s/authorized",node)>=(int)sizeof(path))return 0;
    return small_read(path,buf,sizeof(buf))&&!strcmp(buf,"1");
}
static int authorize_once(const char *node) {
    char path[PATH_MAX],buf[32];
    if(snprintf(path,sizeof(path),"%s/authorized",node)>=(int)sizeof(path))return 0;
    if(!small_read(path,buf,sizeof(buf)))return 0;
    if(!strcmp(buf,"1"))return 1;
    if(strcmp(buf,"0"))return 0;
    int fd=open(path,O_WRONLY|O_CLOEXEC);if(fd<0)return 0;
    ssize_t n=write(fd,"1\n",2);close(fd);
    printf("GOOGLEBOOK_ROOT: authorization %s result=%zd\n",node,n);
    return n==2&&small_read(path,buf,sizeof(buf))&&!strcmp(buf,"1");
}
static void wait_selected_root(void) {
    FILE *f=fopen("/proc/cmdline","re");char cmd[16384];
    if(!f||!fgets(cmd,sizeof(cmd),f))fail("read kernel command line");
    fclose(f);
    unsigned count=0;int matching=0;char *save=NULL;
    for(char *p=strtok_r(cmd," \t\r\n",&save);p;p=strtok_r(NULL," \t\r\n",&save))
        if(!strncmp(p,"androidboot.boot_part_uuid=",sizeof("androidboot.boot_part_uuid=")-1)) {count++;matching=!strcmp(p+sizeof("androidboot.boot_part_uuid=")-1,SELECTED_SUPER);}
    if(count!=1||!matching){errno=EINVAL;fail("selected Android partition mismatch");}
    struct timespec start,now;clock_gettime(CLOCK_MONOTONIC,&start);
    int attempted=0;
    for(;;) {
        if(selected_super_present()){puts("GOOGLEBOOK_ROOT: selected super partition ready");return;}
        if(!attempted) {
            glob_t g={0};char leaf[PATH_MAX]={0};unsigned matches=0;
            if(glob("/sys/bus/thunderbolt/devices/*",0,NULL,&g)==0)
                for(size_t i=0;i<g.gl_pathc;i++)if(id_is(g.gl_pathv[i],SELECTED_ROUTER)) {
                    matches++;if(!realpath(g.gl_pathv[i],leaf))leaf[0]=0;
                }
            globfree(&g);
            if(matches==1&&leaf[0]&&
               (!strncmp(leaf,"/sys/devices/platform/soc/381ac0000.cio/",sizeof("/sys/devices/platform/soc/381ac0000.cio/")-1)||
                !strncmp(leaf,"/sys/devices/platform/soc/501ac0000.cio/",sizeof("/sys/devices/platform/soc/501ac0000.cio/")-1))) {
                char parent[PATH_MAX];snprintf(parent,sizeof(parent),"%s",leaf);*strrchr(parent,'/')=0;
                int chain=host_node(parent);char dock[PATH_MAX]={0};
                if(!chain&&id_is(parent,SELECTED_DOCK)) {
                    snprintf(dock,sizeof(dock),"%s",parent);*strrchr(parent,'/')=0;chain=host_node(parent);
                }
                if(chain){attempted=1;if(!dock[0]||authorize_once(dock))authorize_once(leaf);}
            }
        }
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-start.tv_sec>=45){errno=ETIMEDOUT;fail("selected external Android disk unavailable after 45s");}
        usleep(200000);
    }
}

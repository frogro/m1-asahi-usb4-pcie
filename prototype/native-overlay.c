#include <linux/module.h>
#include <linux/of.h>
#include "native-blob.h"
static int overlay_id=-1;
extern int apciec_native_node(struct device_node*,struct module*);
static int __init start(void)
{
 struct device_node *np;int ret;
 if(!of_machine_is_compatible("apple,j274") || PAGE_SIZE!=16384)return -ENODEV;
 np=of_find_node_by_path("/soc/pcie@530000000");if(np){of_node_put(np);return -EBUSY;}
 ret=of_overlay_fdt_apply(native_blob,sizeof(native_blob),&overlay_id,NULL);if(ret)goto undo;
 np=of_find_node_by_path("/soc/pcie@530000000");if(!np){ret=-ENODEV;goto undo;}
 ret=apciec_native_node(np,THIS_MODULE);of_node_put(np);if(!ret)return 0;
undo:if(overlay_id>=0)of_overlay_remove(&overlay_id);return ret;
}
static void __exit stop(void){apciec_native_node(NULL,NULL);of_overlay_remove(&overlay_id);}
module_init(start);module_exit(stop);MODULE_LICENSE("GPL");MODULE_DESCRIPTION("Temporary M1 external PCIe firmware nodes for native NVMe test");

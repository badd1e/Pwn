
obj-m += prl_pwn.o

KDIR := /lib/modules/$(shell uname -r)/build
PWD := $(shell pwd)

ccflags-y += -DAEDEBUG=1 -DDUMP_TG_REQUEST

default:
	$(info [*] Building the hypercall detour interface driver...)
	$(MAKE) -C $(KDIR) M=$(PWD) modules KBUILD_EXTRA_SYMBOLS=/usr/lib/parallels-tools/kmods/prl_tg/Toolgate/Guest/Linux/prl_tg/Module.symvers
#	$(MAKE) -C $(KDIR) M=$(PWD) modules KBUILD_EXTRA_SYMBOLS=/usr/src/parallels-tools-16.1.3.49160/prl_tg/Toolgate/Guest/Linux/prl_tg/Module.symvers

load:
	$(info [*] Loading...)
	sudo insmod prl_pwn.ko

unload: 
	$(info [*] Unloading...)
	sudo rmmod prl_pwn.ko

clean:
	$(info [*] Cleanup...)
	rm -rf *.o* *.ko *.mod* *symvers .tmp_versions ".*.cmd" *.ver modules.order *.cache.mk
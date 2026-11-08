# NoMount v2.2.0, dcdab8eee6455677f0b906f28142571b788a5c80 (676 commits).
# Vendored source: keep the upstream version independent of kernel history.
ccflags-y += -DNOMOUNT_COMMIT_COUNT=\"676\"

obj-$(CONFIG_NOMOUNT) += nomount.o
ccflags-y += -std=gnu11 -Wno-declaration-after-statement -O3 -fno-stack-protector

ifeq ($(shell grep -qE '\(\*[[:space:]]*__get\)' $(srctree)/include/linux/xattr.h 2>/dev/null && echo 1 || echo 0),1)
ccflags-y += -DNM_HAS_XATTR__GET
endif

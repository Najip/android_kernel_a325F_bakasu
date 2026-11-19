# NoMount v2.3.1, dcd77d03e9912f397a586d7da81694d1628f170e (785 commits).
# Vendored source: keep the upstream version independent of kernel history.
ccflags-y += -DNOMOUNT_COMMIT_COUNT=\"785\"

obj-$(CONFIG_NOMOUNT) += nomount.o
ccflags-y += -std=gnu11 -Wno-declaration-after-statement -O3 -fno-stack-protector

ifeq ($(shell grep -qE '\(\*[[:space:]]*__get\)' $(srctree)/include/linux/xattr.h 2>/dev/null && echo 1 || echo 0),1)
ccflags-y += -DNM_HAS_XATTR__GET
endif

# NoMount v2.2.0, 71883de7ab2e2468bbbaf78ef64ac44a33069531 (615 commits).
# Vendored source: keep the upstream version independent of kernel history.
ccflags-y += -DNOMOUNT_COMMIT_COUNT=\"615\"

obj-$(CONFIG_NOMOUNT) += nomount.o
ccflags-y += -std=gnu11 -Wno-declaration-after-statement -O3 -fno-stack-protector

ifeq ($(shell grep -qE '\(\*[[:space:]]*__get\)' $(srctree)/include/linux/xattr.h 2>/dev/null && echo 1 || echo 0),1)
ccflags-y += -DNM_HAS_XATTR__GET
endif

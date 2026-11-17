# SPDX-License-Identifier: GPL-2.0
# Loaded after upstream Kbuild, only for drivers/kernelsu with SUSFS enabled.
#
# BakaSU orders preinit.o after its generated syscall header, exposed through
# KSU_SYSCALL_NO_TARGET. KernelSU-Next legacy builds its preinit runner without
# that generator, so when the variable is empty there is nothing to add and this
# file must not fail the build.
ifneq ($(strip $(KSU_SYSCALL_NO_TARGET)),)
ifeq ($(filter preinit/preinit.o preinit/blob.o,$(kernelsu-objs)),preinit/preinit.o preinit/blob.o)
# Upstream registers this object after its generic generated-header dependencies.
$(obj)/preinit/preinit.o: $(KSU_SYSCALL_NO_TARGET)
endif
endif

# Jack priority UID filter migration

- Jack priority implementation, headers and feature-reporting blocks retained.
- Old standalone priority implementation removed from source and Kbuild.
- Priority and sus-path UID filter commands dispatched by parent-kernel glue.
- Reboot priority caller uses Jack double-pointer API, a separate return 0 and a feature guard.
- Existing KernelSU-Next credential, kernel_read and disabled-log adaptations retained.
- Logging configuration unchanged. No defconfig changes.
- This migration does not complete the remaining stat/super/sys hook audit.
- Generated source still needs a kernel build and device runtime testing.

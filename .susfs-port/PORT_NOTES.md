# xxKSU manual-hook review port

- Base: 8e229ae90e5f2499a0a26d3ed98fd7e0e2f52cb7
- Native direct exec and security entry points; automated LSM and branch-link modes disabled.
- Existing access/stat bridge, SUSFS reboot dispatch and native input handler retained.
- Existing parent integration materialized; locked KernelSU patches applied during builds.
- Builder/package configuration checks and workflow routing updated for this isolated branch.
- Existing SUSFS core retained: this is NOT a complete Jack core upgrade.
- Source generation and shell syntax checks only. Compile/link, boot, root and performance remain untested.

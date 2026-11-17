# fgetpriority compatibility patches

The `fgetpriority` submodule (https://github.com/aerath-stuff/fgetpriority) stays an
unmodified upstream checkout, the same rule as `KernelSU` (BakaSU).

Put 4.14 compatibility fixes here as `NNNN-description.patch` files. Paths are relative
to the fgetpriority repo root (e.g. `a/kernel/main.c`). They are applied in sorted order
to a throw-away export of the submodule by `scripts/prepare_fgetpriority.sh`,
never to the submodule itself.

Create a patch:

    cp -a fgetpriority /tmp/fgp-work && cd /tmp/fgp-work
    git init -q && git add -A && git commit -qm base
    # ...edit kernel/*.c / kernel/*.h...
    git diff > ~/NNNN-description.patch

Validate: `sh scripts/prepare_fgetpriority.sh --check`

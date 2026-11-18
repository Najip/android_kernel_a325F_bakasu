# Jack SUSFS 2.4.0 reviewed against existing xxKSU adaptations

- Jack commit: 26f2313be61f7a8603a50b2dcd12171495a79d27
- Baseline patch: bbe032eb06c50d24a9207bf2ece5e25cf2460bd0
- Core decision: existing fs/susfs.c retained. The only patch delta is the SUS_PATH i_state fix, and this tree already has it.
- Priority filter: existing fs/susfs_priority.c and int(void __user *) declaration retained. Jack's void(void __user **) implementation was not mixed in.
- Hook hunks unchanged from the baseline were not reapplied. Exact matches are already_present; context differences against existing adaptations are reviewed_existing_adaptation.
- This is not proof of a successful compile, boot, root or runtime behavior.

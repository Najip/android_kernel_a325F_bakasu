# Pull Request: SUSFS Priority UID Adapter Variant

## Summary

This PR proposes a **variant** of the SUSFS priority UID adapter for BakaSU sync-up integration.

It is intended to be submitted alongside alternative implementations so upstream maintainers can review the trade-offs and choose the approach they prefer.

**Patch file:** `patches/kernel/0001-susfs-add-bakasu-sync-up-priority-adapter.patch`

## What this variant does

- Adds `susfs_parse_priority_app_strings()` to `fs/susfs_priority.c`.
- Declares it in `include/linux/susfs.h`.
- Queues the existing delayed priority refresh (`priority_queue_refresh`) with a 250 ms delay.
- Avoids resolving paths or overriding credentials directly from fsnotify/rename callbacks.

## Variant options

| Option | Approach | Pros | Cons | Status |
|--------|----------|------|------|--------|
| A — Delayed refresh (this PR) | Queue `priority_queue_refresh` with 250 ms delay from package observer / rename hook | Simple, reuses existing kernel refresh path, no path resolution in callback | Slight delay before priority takes effect | Proposed |
| B — Immediate refresh | Call `priority_queue_refresh(0)` directly from the hook | Fastest reaction | May run in sensitive context; higher risk of locking/reentrancy issues | Alternative |
| C — Deferred workqueue | Schedule a dedicated workqueue item to perform the refresh | Fully decoupled from fsnotify context | More code, extra scheduling overhead | Alternative |
| D — Upstream-native | Let upstream implement its own preferred mechanism | Cleanest long-term | Requires upstream design decision | Open |

## Recommended choice

- **Preferred:** Option A — delayed refresh.
- **Reason:** It is the least invasive, matches the existing SUSFS refresh pattern, and avoids doing filesystem work directly inside fsnotify/rename callbacks.

## Build / test status

- [x] Patch applies cleanly with `git apply`.
- [x] Kernel builds successfully with AOSP Clang 14.
- [x] `susfs_parse_priority_app_strings` symbol present in `vmlinux`.
- [x] No regression in existing SUSFS priority UID behavior.

## Upstream decision requested

Please review the options above and indicate which approach you prefer:

- [ ] Option A — Delayed refresh (recommended)
- [ ] Option B — Immediate refresh
- [ ] Option C — Deferred workqueue
- [ ] Option D — Upstream-native design
- [ ] Other (please describe)

## Additional notes

- This adapter is intentionally minimal and non-invasive.
- It does not modify BakaSU userspace behavior.
- It only wires the existing kernel-side delayed refresh into the sync-up hooks.
- If upstream prefers a different mechanism, this PR can be adapted or withdrawn in favor of the chosen design.

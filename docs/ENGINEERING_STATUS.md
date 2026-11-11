# Engineering status — 0.3.0

Hyrule is an optimization overlay for Hookshot, not a replacement for its entire ARM64 lifter or Vulkan runtime. This document distinguishes working code from future renderer/compiler work.

## CPU/GPU synchronization

Implemented: scripts/run_gpu_profile.ps1 launches the local game with controlled Vulkan runtime variables and saves frame-time CSV plus Hookshot logs. hyrulefast.profile_report extracts batched-submit flush reasons, slow-frame samples, fine replay timings and related log evidence.

Upstream: Hookshot already has batched queue submissions and a configurable poll-flush age in gpu/vk/vk_replay.cpp. Selecting those settings is not a new scheduler.

Not implemented: an adaptive queue scheduler. It must be validated against timeline semaphore ordering on target drivers; delaying the wrong flush can stall or deadlock producer/consumer work.

## Shared-memory and memory traffic

Implemented: log analysis for dirty-page captures, live/old page refreshes, write-back diff bytes and fine-grained storage-buffer/descriptor timings.

Upstream: gpu/vk/vk_memory.cpp has host-imported guest pools, optional device-local mirrors, dirty-page capture and write-back diffing. The upstream history documents performance-sensitive write-watch behavior, including a slower read-before-write experiment.

Not implemented: a new dirty-page coalescer or smarter mirror-lifetime policy. Any such change must preserve writes racing with submission capture and CPU visibility of GPU-written data. Compare memory contents and page sets, not FPS alone.

## Mesh fallback

Implemented: hyrulefast.mesh_fallback.inspect_source detects the upstream fallback_record count-buffer rejection; the log parser detects associated runtime messages. docs/MESH_FALLBACK_DESIGN.md records invariants and tests.

Known gap: the compute fallback can translate task/mesh programs into compute work and render generated vertex records, but currently rejects draws with a non-null DrawArgs.count_addr.

Not implemented: GPU-resident multi-draw execution for indirect-count commands. The count must stay GPU-resident; each draw needs correct per-draw argument addressing, task/mesh metadata, allocator ranges and Vulkan barriers. CPU readback is intentionally rejected because it inserts a synchronization stall.

## ARM64 to x86-64 translation

Implemented: the profile-hot loop-poll experiment in hyrulefast.pollpass, profile-hot selection from Hookshot's generated function list, an LLVM PGO workflow and configurable host CPU/hot-code optimization options. Interval 1 preserves upstream behavior.

Not implemented: a new ARM64 instruction selector or register allocator. Hookshot's a64-kit lift currently emits C and relies on Clang/LLVM for final x86-64 instruction selection and register allocation. A translator-side rewrite needs differential tests against Unicorn and full guest-state equivalence.

## Validation before calling something faster

1. Same PC, driver, game build, save, route, display mode, frame cap and shader-cache state.
2. At least three alternating baseline/variant runs; discard loading and shader warm-up.
3. Compare median, p95/p99 frame time and approximate 1% lows.
4. Compare submit reasons, fine timings, dirty-page counts and write-back bytes.
5. Check visuals, sound, game speed, inputs, save state, thread handoffs and long-run stability.
6. Keep a variant only when repeated runs improve the target metric without correctness regressions.

No Radeon 680M gameplay result is claimed by the source-level test suite.

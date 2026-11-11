# Engineering status — 0.4.0

Hyrule is an optimization overlay for Hookshot, not a replacement for its entire ARM64 lifter or Vulkan runtime.

## Background workers and CPU/GPU policy

Implemented: Hookshot already translates shaders and builds Vulkan pipelines asynchronously on below-normal-priority background workers. Hyrule now sets a hardware-aware worker budget and dynamically gates how many of those workers may execute concurrently. RX_VK_WORKERS=1..8 overrides the baseline; RX_VK_ADAPTIVE_WORKERS=0 disables the governor.

Every 120 presents, Hookshot's existing Vulkan timestamp queries provide accumulated GPU execution time. Hyrule compares the average GPU time per frame against elapsed wall-clock frame time. At 80% pressure the worker limit drops by one; at 92% it drops further (two workers on integrated GPUs, one on discrete GPUs); below 68% it returns to the baseline. The gap between thresholds provides hysteresis. Reducing the worker limit does not interrupt a running compile or change Vulkan queue/timeline ordering.

The default budget is capped at four workers for integrated GPUs and six for discrete GPUs. The Ryzen 7 6800H has 16 logical threads and its Radeon 680M is integrated, giving a four-worker baseline. This is a conservative starting point; only target-hardware profiling can establish whether it improves frame times.

## Host CPU target and AVX2

Implemented: the build wrapper recognizes selected Zen 3/3+ Ryzen processors, including Ryzen 7 6800H, and selects -march=znver3. If CPU model detection fails or the processor is not in the list, Hookshot's CPUID-based x86-64 target selection remains active.

Hookshot's existing copy_nt capture helper is compiled with an AVX2 implementation when __AVX2__ is defined (256-bit loads and streaming stores), and with a 128-bit SSE implementation otherwise. Hyrule exposes the existing RX_VK_CAPTURE_NT opt-in in its profile script. It remains opt-in because upstream measurement on a discrete GPU did not show consistent gains. Hyrule does not add a second, unused SIMD copy routine.

This is CPU-specific code generation, not a portable fat binary. Do not move a znver3 build to a CPU that lacks the selected instruction set.

## CPU/GPU synchronization

Implemented: the worker governor uses measured GPU/frame pressure to limit background CPU compilation contention. Profiling tools retain submit flush reasons, queue waits and per-frame GPU time. Hookshot already has batched queue submissions and configurable poll-flush timing.

Not implemented: a new adaptive Vulkan queue-submit scheduler. Timeline semaphore ordering and resource visibility need separate driver validation; changing arbitrary waits can stall producers or consumers.

## Shared-memory and memory traffic

Implemented: log analysis for dirty-page captures, live/old page refreshes, write-back diff bytes and fine-grained descriptor/replay timings. The existing AVX2 non-temporal copy can reduce cache pollution in the particular capture path when enabled and beneficial.

Not implemented: a new dirty-page coalescer or mirror-lifetime policy. Any change must preserve writes racing with submission capture and CPU visibility of GPU-written data.

## Mesh fallback

Implemented: source inspection and log analysis detect the known indirect-count fallback gap.

Known gap: the compute mesh fallback rejects draws with a non-null DrawArgs.count_addr. GPU-resident multi-draw execution still needs correct per-draw task inputs, allocator ranges and Vulkan barriers. CPU readback is deliberately not used because it can force a GPU synchronization stall.

## ARM64 to x86-64 translation

Implemented: profile-hot loop-poll experiment, hot-function selection, LLVM PGO workflow and host CPU-target selection.

Not implemented: a new ARM64 decoder, instruction selector or register allocator. Hookshot's current lift emits C and relies on Clang/LLVM for final x86-64 instruction selection and register allocation.

## Validation before calling something faster

1. Same PC, driver, game build, save, route, display mode, frame cap and shader-cache state.
2. At least three alternating baseline/variant runs; discard loading and shader warm-up.
3. Compare median, p95/p99 frame time and approximate 1% lows.
4. Compare GPU time, replay time, queue submit reasons, dirty-page counts and write-back bytes.
5. Check visuals, sound, game speed, inputs, save state, thread handoffs and long-run stability.
6. Keep a variant only when repeated runs improve the target metric without correctness regressions.

No Radeon 680M gameplay result is claimed by the source-level test suite.

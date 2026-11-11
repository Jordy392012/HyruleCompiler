# Roadmap — Remaining Work After v0.4.0

This document tracks work that is **not implemented or not yet validated** in Hyrule Native Compiler. It is intentionally separate from the v0.4.0 implementation notes: an item listed here must not be treated as completed just because supporting instrumentation or documentation exists.

## Current baseline

The v0.4.0 branch includes the GPU-pressure-aware background compiler worker governor, configurable worker limits, Zen 3 targeting for recognized Ryzen CPUs such as the Ryzen 7 6800H, controls for Hookshot's existing non-temporal capture-copy path, profiling utilities, and Python tests.

The GitHub `python-tests` workflow validates the Python tooling. It does **not** compile the modified Hookshot C++/Vulkan renderer, launch the Windows game build, or prove an FPS improvement on a Radeon 680M. No performance gain is claimed until repeatable target-hardware measurements exist.

## Priority 0 — Validate the current v0.4.0 work

### 0.1 Native Windows / Vulkan build and runtime validation
- [ ] Build the patched Hookshot C++ sources with the actual Windows toolchain and Vulkan dependencies.
- [ ] Confirm the worker-governor patch applies cleanly to the pinned Hookshot revision and fails safely when source anchors drift.
- [ ] Launch the resulting native game build and verify shader compilation, pipeline creation, rendering, input, audio, save/load, and long-session stability.
- [ ] Record compiler version, Hookshot revision, GPU driver, game build, and all run settings.

**Done when:** the patched native build compiles and completes a repeatable runtime smoke test without regressions. Passing Python tests alone does not satisfy this item.

### 0.2 Radeon 680M performance A/B testing
- [ ] Benchmark on the target Ryzen 7 6800H / Radeon 680M machine using the same scene, route, resolution, display mode, driver, frame cap, and shader-cache state.
- [ ] Compare fixed worker budgets (including the four-worker baseline) against adaptive workers enabled and disabled.
- [ ] Compare `CaptureNonTemporal=auto`, `on`, and `off` while keeping other settings fixed.
- [ ] Run at least three alternating repetitions per variant after shader warm-up; report median, p95, p99, and approximate 1% low frame times.
- [ ] Include GPU time, queue waits/flush reasons, and relevant capture/write-back counters where available.
- [ ] Check visual correctness, audio, input responsiveness, and stability—not just the highest FPS sample.

**Done when:** raw logs/CSVs and a repeatable comparison report are committed, and defaults are chosen from measured results. If a change does not help consistently, keep it opt-in or revert it.

## Priority 1 — Renderer scheduling and memory work

### 1.1 Adaptive Vulkan queue-submission scheduler
- [ ] Investigate whether queue-submission timing is a meaningful bottleneck after the worker governor is measured.
- [ ] Design a scheduler that preserves semaphore/fence dependencies, producer-consumer ordering, resource visibility, and Vulkan barriers.
- [ ] Prototype behind an opt-in switch and compare against the unmodified Hookshot submission path.
- [ ] Add stress tests for stalls, ordering, resource lifetime, and sustained gameplay.

**Risk / constraint:** changing queue waits or submission order without modeling dependencies can stall producers/consumers or introduce synchronization bugs. Do not implement speculative wait changes just to reduce a counter.

### 1.2 Dirty-page coalescing and mirror-lifetime policy
- [ ] Design a dirty-page coalescer for capture/write-back traffic.
- [ ] Define when mirrored pages are created, refreshed, retained, and released.
- [ ] Preserve correctness when guest writes race with capture, submission, replay, and CPU visibility.
- [ ] Measure page counts, bytes copied, write-back traffic, and frame-time impact before and after.

**Risk / constraint:** this must preserve data visibility and write ordering. The current project has profiling/analysis for dirty-page traffic, but it does not implement a new coalescer or mirror-lifetime policy.

### 1.3 Mesh fallback: indirect-count draws
- [ ] Add support for the compute-mesh fallback case where `DrawArgs.count_addr` is non-null.
- [ ] Keep draw-count and argument data GPU-resident; do not introduce a CPU readback stall as a shortcut.
- [ ] Validate per-draw task inputs, allocator ranges, Vulkan barriers, and multi-draw execution.
- [ ] Add regression coverage for both null and non-null `count_addr` cases.

**Done when:** the fallback handles the indirect-count case correctly and repeatably without CPU readback or visual regressions.

## Priority 2 — Translation architecture

### 2.1 ARM64 translation frontend/backend expansion
- [ ] Specify the desired ARM64 instruction coverage and define a test corpus.
- [ ] Investigate a dedicated decoder and intermediate representation rather than relying only on the current lift-to-C path.
- [ ] Design instruction selection and register allocation only after the IR and correctness tests are established.
- [ ] Compare generated code correctness and performance against the current Clang/LLVM-based path.

**Current state:** Hookshot currently lifts ARM64 code to C and relies on Clang/LLVM for final x86-64 instruction selection and register allocation. A new ARM64 decoder, instruction selector, and register allocator are not part of v0.4.0. This is a larger architectural project, not a small optimization patch.

## Priority 3 — Ongoing quality and release work

- [ ] Add a Windows CI job that builds the native patched renderer, in addition to the existing Python test job.
- [ ] Add a reproducible integration/smoke-test procedure for fresh Hookshot checkouts and source-version drift.
- [ ] Keep performance claims tied to checked-in benchmark artifacts and documented test conditions.
- [ ] Re-run the test suite and update this roadmap whenever a task is completed, deferred, or abandoned.

## Explicitly outside the current roadmap

A CPU software renderer is not currently planned. The target system already has a Radeon 680M GPU, and moving rasterization to the CPU is not assumed to improve performance. GPU-generated draw counts also remain GPU-resident; CPU readback is not an intended workaround for the mesh fallback gap.

## Completion policy

Do not mark a task complete because a patch compiles in isolation or because a source-level unit test passes. Renderer changes require native-build validation, correctness checks, and measurements on representative hardware. Performance-sensitive defaults require repeated A/B evidence.

# Hyrule Native Compiler — Optimization Lab (0.4.0)

Hyrule is an optimization overlay for the local Hookshot static recompilation project. It does not include game assets, keys, ROMFS, executable dumps, or built game output.

## Windows executable

The Hyrule Windows setup application is available from the [GitHub Releases page](https://github.com/Jordy392012/HyruleNativeCompiler/releases).
It is a single-file HyruleBuilder.exe; on first launch it downloads the official Hookshot v2.0.14 compiler packages and verifies their
SHA-256 checksums before building locally. No separate Python installation is required.

The application needs the supported Switch 2 game dump in .nup format or both romfs and exefs folders. It does not accept an original
N64 .z64 ROM and does not include or upload copyrighted game files. See docs/BUILD_WINDOWS.md for requirements and instructions.

## Scope

Hookshot supplies the ARM64-to-x86-64 lifter and Vulkan renderer. Hyrule adds checked integration for a profile-hot generated-C poll pass, CPU-target tuning, a GPU-pressure-aware background worker governor, and repeatable A/B profiling. It is not a replacement ARM64 decoder, instruction selector, register allocator, or Vulkan backend.

## Implemented in v0.4.0

- Profile-hot-function-scoped loop-poll decimation. Interval 1 preserves upstream polling; larger intervals are experimental and may delay guest thread handoff.
- Checked installer with source anchors and backups for every modified Hookshot source file.
- CPU-target selection: recognized Ryzen Zen 3/3+ processors, including the Ryzen 7 6800H, use -march=znver3. Other CPUs retain Hookshot's CPUID-based target selection.
- Configurable background shader/pipeline compilation concurrency. Hookshot already performs shader translation and pipeline builds asynchronously; Hyrule controls the maximum number of those existing workers.
- Adaptive CPU/GPU workload governor: Vulkan GPU timestamps every 120 presents throttle background compilation when the GPU is saturated, then restore workers after headroom returns.
- Worker override: RX_VK_WORKERS=1..8; disable adaptive throttling with RX_VK_ADAPTIVE_WORKERS=0.
- Profile tools for frame-time CSVs, GPU busy estimates, queue-submit reasons, dirty-page/write-back traffic and worker-count A/B comparisons.
- An opt-in switch for Hookshot's existing non-temporal guest-memory capture copy: RX_VK_CAPTURE_NT=1.

## CPU/GPU scheduling

The aim is to keep rendering work on the GPU while controlling background shader/pipeline work on the CPU. Hyrule does not move rasterization or GPU-generated draw counts to the CPU, and it does not add CPU readbacks.

Without an override, an integrated-GPU system starts with ceil(logical_threads / 4) background workers, clamped to 2–4. A discrete-GPU system uses ceil(logical_threads / 3), clamped to 2–6. The GPU-pressure governor steps down when recent GPU execution time exceeds 80% of elapsed frame time, steps down further above 92%, and restores the baseline below 68%. Hysteresis avoids rapid worker-count oscillation. This pool is for background compilation, not the guest's emulated CPU threads.

The Ryzen 7 6800H has 16 logical threads, so the integrated-GPU baseline is four background workers. It can temporarily reduce to three or two during GPU-heavy scenes. The profile script's Workers option lets you test explicit values rather than assuming more workers are faster.

## AVX2 path and fallback

Hookshot already contains an x86 non-temporal capture-copy helper. When compiled with AVX2 enabled, that helper uses 256-bit AVX2 loads and streaming stores; when the build target does not enable AVX2, it uses the 128-bit SSE path. The build wrapper selects znver3 for recognized Zen 3/3+ Ryzen CPUs such as the 6800H, which enables Clang's AVX2 code generation for this machine. Other systems keep Hookshot's detected target, so a CPU without AVX2 does not receive AVX2-only code.

The non-temporal copy is opt-in because upstream measurements on a discrete GPU did not show a consistent improvement. Hyrule exposes it for testing; it is not forced on. Compare it with CaptureNonTemporal auto and CaptureNonTemporal on using the same scene and at least three alternating runs.

## Install

Requirements: Windows 10/11, Python 3.10+, a local Hookshot checkout and the toolchain/dependencies required by Hookshot.

    python -I scripts/install_optimizer.py C:\path\to\Hookshot

Then rebuild the existing game folder:

    powershell -ExecutionPolicy Bypass -File scripts/build_variant.ps1 -HookshotRoot C:\path\to\Hookshot -GameFolder C:\Games\OcarinaNative -PollInterval 1 -CpuTarget auto

The build wrapper recognizes the 6800H and selects znver3. Otherwise it leaves RX_MARCH unset and Hookshot's CPUID-based target selection remains in charge. Builds are machine-targeted; do not move a znver3 build to a CPU that lacks that ISA.

## Profiling worker and AVX2 settings

Example on the 6800H / Radeon 680M:

    powershell -ExecutionPolicy Bypass -File scripts/run_gpu_profile.ps1 -GameFolder C:\Games\OcarinaNative -RunName workers4 -Workers 4 -AdaptiveWorkers on -CaptureNonTemporal auto

Repeat with Workers 3, Workers 5, and CaptureNonTemporal on. Keep route, resolution, driver, upscaler, frame cap, save and shader-cache state identical. Compare CSVs:

    python -I scripts/frame_report.py profiles\workers4.csv
    python -I scripts/frame_report.py profiles\workers5.csv --compare profiles\workers4.csv

Get a suggested worker value using the matching log and CSV:

    python -I scripts/recommend_cpu_policy.py profiles\workers4.log --frame-csv profiles\workers4.csv --gpu-type integrated --threads 16

Alternate baseline/variant runs at least three times. Keep a setting only when median and tail frame times improve without visual or stability regressions. The governor reads GPU timestamps every 120 presents; the recommendation script is a starting point, not a promise of higher FPS.

## Known limits

- CPU software rendering is not added. The Radeon 680M is designed for parallel graphics work; moving rasterization to the CPU would usually be a regression.
- GPU-generated draw counts stay on the GPU; no CPU readback is used as a workaround.
- Background shader translation/pipeline compilation is Hookshot's existing implementation; Hyrule controls its worker concurrency.
- Mesh-fallback indirect-count support remains a separate renderer-engineering task. The source inspection still reports that gap rather than claiming it is solved.
- A new dirty-page coalescer and a new ARM64 decoder/selector/register allocator are not included.

## Tests

    python -m unittest discover -s tests -v

These source-level tests are not a complete Windows build or a Radeon 680M gameplay benchmark. No FPS gain is claimed without target-hardware A/B evidence.

## Licensing

The Hyrule overlay is MIT-licensed. Hookshot and its dependencies retain their own licenses and notices. Never commit game dumps, keys or generated copyrighted game files.

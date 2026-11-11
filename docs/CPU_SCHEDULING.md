# CPU scheduling, GPU pressure and AVX2 capture

## Background compilation worker pool

Hookshot already runs shader translation and Vulkan pipeline creation asynchronously on below-normal-priority worker threads. Hyrule retains that path and controls the maximum number of concurrent jobs; it does not create a duplicate compiler or interrupt a running compile.

RX_VK_WORKERS=1..8 chooses the baseline worker count. Without an override, integrated GPU systems use ceil(logical_threads / 4), clamped to 2–4; discrete GPU systems use ceil(logical_threads / 3), clamped to 2–6.

Every 120 presents, Hookshot's GPU timestamp query provides the recent average GPU execution time per frame. The governor divides this by elapsed wall-clock frame time:
- At or above 80%, reduce the limit by one worker.
- At or above 92%, reduce by two workers on integrated GPUs or one on discrete GPUs.
- At or below 68%, restore the baseline.
- Between 68% and the active throttle threshold, hold the previous setting.

RX_VK_ADAPTIVE_WORKERS=0 disables dynamic throttling. The governor changes only how many background compile jobs may execute simultaneously; it does not change GPU queue ordering, waits, barriers, guest execution, or draw counts.

For the Ryzen 7 6800H (8 cores / 16 logical threads) with Radeon 680M, the integrated-GPU default is four background workers. It can temporarily reduce to three or two when GPU time approaches frame time.

## AVX2 and fallback

The existing Hookshot copy_nt helper streams captured guest-memory pages to memory using non-temporal stores. Its AVX2 build path uses two 256-bit loads and streaming stores per 64-byte line. When compiled without __AVX2__, it uses four 128-bit SSE loads and streaming stores instead.

Hyrule's build wrapper selects -march=znver3 for recognized Zen 3/3+ processors including the 6800H, which defines __AVX2__ for this translation unit. If CPU detection fails or the CPU is not recognized, Hookshot's own CPUID target logic remains in charge and can use the lower-ISA implementation. Builds are machine-targeted; a znver3 build should not be moved to an older CPU.

The non-temporal path remains off unless RX_VK_CAPTURE_NT=1 because it has not helped every GPU. It bypasses normal cache allocation for full cache lines, which can help when the destination is handed to the GPU and not read by the CPU, but can also lose on other memory systems and sizes. RX_VK_CAPTURE_NT=0 or an unset value uses ordinary memcpy.

## Measuring on the 680M

Capture otherwise identical runs with:

    powershell -ExecutionPolicy Bypass -File scripts/run_gpu_profile.ps1 -GameFolder C:\Games\OcarinaNative -RunName nt_off -Workers 4 -CaptureNonTemporal off
    powershell -ExecutionPolicy Bypass -File scripts/run_gpu_profile.ps1 -GameFolder C:\Games\OcarinaNative -RunName nt_on -Workers 4 -CaptureNonTemporal on

Also compare worker budgets 3/4/5 with non-temporal capture held constant. Use the same save, scene route, resolution, upscaler, frame cap, shader cache and driver. Alternate variants at least three times. Compare median and p95/p99 frame time, not one best FPS reading.

The recommendation utility accepts the matching log and frame CSV:

    python -I scripts/recommend_cpu_policy.py profiles\nt_on.log --frame-csv profiles\nt_on.csv --gpu-type integrated --threads 16

It reports an estimated worker setting from GPU time versus median frame time; the in-game governor continues adapting every reporting interval.

## Limits

This is not CPU software rendering. GPU-generated draw counts remain GPU-resident and are never read back by the CPU as a substitute for an indirect-count mesh fallback. A separate dirty-page coalescer, adaptive queue-submit scheduler, and a new ARM64 instruction selector/register allocator remain future renderer/compiler work. No FPS gain is claimed without actual 680M A/B measurements.

# Hyrule Native Compiler — Optimization Lab (0.3.0)

This is a compiler/runtime optimization overlay for the local Hookshot static recompilation project. It is not a preset launcher and it does not include game assets, keys, ROMFS, executable dumps, or built game output.

## Scope

The ARM64-to-x86-64 lifter and Vulkan runtime are provided by the upstream GPL-licensed Hookshot project. Hyrule adds an experimental generated-C loop-poll pass, profiling and A/B tooling, a Zen 3 target option, diagnostics for Vulkan synchronization and guest-memory traffic, and a design/test plan for completing the compute mesh fallback.

It is not yet an independent ARM64 recompiler or a replacement Vulkan backend.

## Implemented

- Profile-hot-function-scoped loop-poll decimation. Interval 1 preserves upstream polling. Intervals 2/4/8/16 are experimental and may delay thread handoff.
- A checked installer that patches only a known Hookshot source layout and saves a backup.
- Build helper for CPU target, hot-code optimization level and optional PGO profile.
- Vulkan queue/submit and dirty-page/write-back log analysis.
- Repeatable GPU-profile and frame-time comparison scripts.
- Mesh-fallback source inspection that explicitly reports the indirect-count limitation.
- Unit tests and a Windows CI workflow.

## Research still required

The adaptive CPU/GPU queue scheduler, new dirty-page coalescer, complete GPU-resident indirect-count mesh fallback and new ARM64 instruction selector/register allocator are not implemented yet. The engineering status and mesh-fallback design documents distinguish these targets from working code.

## Install

Requirements: Windows 10/11, Python 3.10+, a local Hookshot checkout and the toolchain/dependencies required by Hookshot. See the Hookshot development guide:

https://github.com/NotRexed/Hookshot/blob/main/docs/development.md

Run from this folder:

    python -I scripts/install_optimizer.py C:\path\to\Hookshot

Then build a baseline variant:

    powershell -ExecutionPolicy Bypass -File scripts/build_variant.ps1 -HookshotRoot C:\path\to\Hookshot -GameFolder C:\Games\OcarinaNative -PollInterval 1 -CpuTarget auto

The game folder must already be a valid local Hookshot build generated from your own dump. Hyrule does not extract or distribute game data.

## Ryzen 7 6800H experiment

The recommended starting point is interval 1 with automatic CPU targeting. Profile the same gameplay route, then compare Zen 3-targeted and interval 2/4/8 builds. Use identical resolution, upscaler, frame cap, driver, save, route and shader-cache state. Run at least three alternating baseline/variant captures. Keep an optimization only when frame-time data and correctness checks show a repeatable improvement.

The Radeon 680M is an integrated GPU. CPU compiler flags cannot fix a GPU-driver failure, a Vulkan feature gap, or memory-bandwidth saturation. The included Vulkan tools are intended to identify which resource is limiting the run.

## Tests

    python -m unittest discover -s tests -v

The tests are source-level checks, not a full Windows game build or a 680M gameplay benchmark. No game-FPS improvement is claimed without target-hardware A/B evidence.

## Licensing

The Hyrule overlay is MIT-licensed. Hookshot and its dependencies retain their own licenses and notices. Review upstream licenses before combining or redistributing code. Never commit game dumps, keys or generated copyrighted game files.

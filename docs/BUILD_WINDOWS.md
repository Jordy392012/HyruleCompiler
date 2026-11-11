# Hyrule Builder for Windows

Hyrule Builder is a single-file Windows setup application. It packages the Hyrule launcher and its Python runtime into HyruleBuilder.exe.
On first launch it downloads the official Hookshot v2.1.0 build-tool packages over HTTPS and checks every package against the
SHA-256 values in Hookshot's release manifest. No separate Python installation is required.

## Important: accepted game files

This tool builds the supported Switch 2 game dump accepted by Hookshot. It does not accept the original N64 .z64 / .n64 ROM format.
Choose either your own supported .nup dump, or both extracted romfs and exefs folders. The upstream builder validates program/version
before it begins. This project does not distribute game data, keys, a ready-made game executable, or instructions for obtaining
copyrighted game files.

## Requirements

- 64-bit Windows 10 or Windows 11.
- A supported game dump that passes Hookshot's version check.
- An internet connection on first run (roughly 500 MB of tool packages).
- About 60 GB of free disk space while building; an SSD is strongly recommended.
- 16 GB RAM or more.
- A Vulkan 1.3 graphics driver and GPU with mesh-shader support. Hookshot's current documentation lists NVIDIA RTX 20-series or newer,
  AMD Radeon RX 6000-series or newer, and Intel Arc. A Radeon 680M iGPU is not explicitly listed by upstream compatibility notes;
  check the installed driver's Vulkan mesh-shader support before expecting it to run. The builder cannot add a missing GPU feature.

## Renderer fixes included in Hookshot 2.1.0

The updated upstream renderer includes several changes relevant to texture glitches and intermittent failures:

- Flushes completed texture-upload staging slices before the GPU reads them, including CPU-converted and ASTC uploads.
- Keeps transient image-view allocation failures out of the permanent cache so a later request can retry.
- Publishes failed/completed resource-job state when a background job throws, instead of leaving a waiter stuck or allowing the
  exception to terminate the process.
- Improves recovery around partial frame-interpolation resource setup and failed swapchain replacement.
- Keeps cutscene/movie cues synchronized with their movie when running above a 60 FPS cap.

These are fixes in the official Hookshot v2.1.0 release that Hyrule now installs; Hyrule does not patch the renderer's texture
code itself. They match several plausible causes of missing textures or cutscene crashes, but they cannot guarantee a fix for
every driver-specific problem. The Radeon 680M still needs an in-game test on the target PC. If a particular cutscene still
fails, keep its Hookshot log from that run so the remaining failure can be identified.

## Use

1. Download HyruleBuilder.exe from the Hyrule Native Compiler GitHub Releases page.
2. Run it. Windows may show an unsigned-app warning because this community build is not code-signed.
3. Select your .nup file, or both extracted folders.
4. Choose the output folder and language. Leave shader preparation enabled for the first build.
5. Press Build Hyrule. The launcher installs and checksum-verifies the official toolchain, applies Hyrule's checked poll-pass and
   adaptive Vulkan-worker patches, validates the input, and invokes the native build.
6. Use Launch game when the build finishes.

The compiler and tool packages are installed under %LOCALAPPDATA%\HyruleBuilder. Your selected game dump remains at its original
location and is read locally. The dump is never sent to GitHub by this application.

## Hyrule build policy

- Poll interval defaults to 1, which preserves upstream polling behavior.
- The background Vulkan compile-worker governor is enabled, using GPU-pressure measurements wired into the pinned Hookshot source.
- The build selects znver3 only for recognized Zen 3 / Zen 3+ CPU models (including Ryzen 7 6800H). Other CPUs retain Hookshot's
  CPUID-based selection.
- Non-temporal capture copy remains opt-in. The launcher does not force RX_VK_CAPTURE_NT=1.
- The launcher is pinned to Hookshot v2.1.0. It deliberately refuses automatic upstream-version updates until Hyrule patch anchors
  are checked against that version.

## Build and verification

The Windows release workflow runs the Python test suite, checks patch compatibility against a fresh Hookshot v2.1.0 checkout, builds
the one-file EXE, runs its packaged self-test, then runs the EXE's bootstrap check. The bootstrap check downloads and SHA-256-verifies
the official tool packages and confirms that the patched compiler CLI starts. It does not build a game because CI does not possess the
user's private game dump.

See ROADMAP.md for outstanding native-game runtime and Radeon 680M performance validation.

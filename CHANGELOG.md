# Changelog

## 0.6.0-beta.1

### Updated
- Pin the Windows builder to official Hookshot v2.1.0.
- Refresh upstream source hashes and verify Hyrule's poll-pass and Vulkan worker patches against the v2.1.0 source.
- Update the Windows CI compatibility check and release packaging workflow.

### Renderer fixes inherited from Hookshot 2.1.0
- Publish texture staging uploads before GPU reads.
- Retry transient texture image-view allocation failures.
- Recover background resource jobs when they fail.
- Harden frame-interpolation resource setup and swapchain replacement.
- Keep cutscene/movie cues aligned above a 60 FPS cap.

### Validation
- The release workflow runs the source tests, applies Hyrule patches to a clean Hookshot v2.1.0 checkout, builds the Windows
  executable, checks its self-test, verifies official tool packages, and starts the compiler CLI.
- A full game build and Radeon 680M gameplay/cutscene validation require the user's own supported game dump and target PC.

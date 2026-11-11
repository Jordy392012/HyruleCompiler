# GPU-resident multi-draw support for the mesh fallback

## Existing limitation

On devices without VK_EXT_mesh_shader, Hookshot translates guest task/mesh stages into compute shaders. Mesh workgroups write per-corner records into a shared device-addressable buffer; a generated ordinary vertex stage reads those records and a fallback indirect vertex draw consumes them.

The current fallback_record(VkCommandBuffer, Program&, const DrawArgs&) path rejects a draw when DrawArgs.count_addr is non-zero. That means the guest supplied an indirect-count list whose valid command count is produced by the GPU.

## Why CPU readback is not acceptable

Reading the count buffer on the CPU requires waiting for the GPU to finish the write. It turns an asynchronous GPU command sequence into a CPU/GPU synchronization point. That is likely to hurt precisely on lower-end integrated GPUs. Hyrule does not add a CPU readback workaround.

## Required GPU-side design

A correct implementation needs to preserve these invariants:

1. Count stays GPU-resident. Each draw ordinal is compared against the indirect count on the GPU.
2. Per-draw argument addressing. Each dispatch reads its own group-count and first-group values using the guest stride.
3. Task/mesh pairing. Task payload and meshlet-slot metadata belong to the matching draw and cannot be reused before consumption.
4. One accumulated record range. The allocator and final indirect vertex count cover each accepted draw exactly once, bounded by fallback capacity.
5. Queue ordering. Transfer fills, count reads, task dispatches, mesh dispatches and the final vertex draw use explicit Vulkan barriers.
6. No CPU serialization. No mapped count readback and no queue/device idle wait in the frame path.

A likely direction is a GPU multi-draw expansion stage that emits compact dispatch arguments and per-command metadata. The task and mesh fallback stages then consume that compact list and append to a shared output allocator. Exact placement depends on the existing descriptor and push-constant layout and target-driver capabilities.

## Test matrix

- direct mesh draw, with and without task stage;
- indirect mesh draw with one or multiple commands;
- count values 0, 1, middle of max and max;
- zero group count mixed with non-zero commands;
- non-zero first group and non-default argument stride;
- allocator near capacity;
- two fallback programs interleaved on one recording thread;
- AMD RADV, Windows AMD driver and NVIDIA fallback device.

Compare visible draws, record counts and per-vertex attributes against the native mesh-shader path. FPS-only tests cannot establish correctness.

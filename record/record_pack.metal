// Metal Shading Language compute kernels for ANR texture recording (FORMAT_METAL.md).
// Compiles with MSL 3.0+ for Apple Silicon (M1/M2/M3/M4) with SIMDgroup acceleration.

#include <metal_stdlib>
using namespace metal;

struct RecordParams {
    uint width;
    uint height;
    uint kinds;
    uint flags;
    uint table;
    uint channels;
    uint value;
    uint slot;
};

constant uint REC_DEPTH = 1;
constant uint REC_REFERENCE = 2;
constant uint REC_SRGB = 4;

inline float3 linear_to_srgb(float3 l) {
    l = saturate(l);
    return select(1.055f * pow(l, 1.0f / 2.4f) - 0.055f, l * 12.92f, l <= 0.0031308f);
}

kernel void record_init(constant RecordParams& rp [[buffer(0)]],
                        device uint* record_slot  [[buffer(1)]],
                        uint3 id                  [[thread_position_in_grid]]) {
    if (id.x == 0 && id.y == 0 && id.z == 0) {
        record_slot[0] = rp.value;
    }
}

kernel void record_done(constant RecordParams& rp   [[buffer(0)]],
                        device uint* record_slot    [[buffer(1)]],
                        device uint* record_status  [[buffer(2)]],
                        uint3 id                    [[thread_position_in_grid]]) {
    if (id.x == 0 && id.y == 0 && id.z == 0) {
        const uint used = record_slot[0];
        record_status[2 * rp.slot] = used;
        record_status[2 * rp.slot + 1] = rp.value;
    }
}

// Compute kernel for 8x8 tile encoding into chunk slots
kernel void record_pack(constant RecordParams& rp    [[buffer(0)]],
                        texture2d<float, access::sample> src  [[texture(0)]],
                        texture2d<float, access::sample> src2 [[texture(1)]],
                        device atomic_uint* record_slot       [[buffer(1)]],
                        uint3 threadgroup_position_in_grid    [[threadgroup_position_in_grid]],
                        uint3 thread_position_in_threadgroup  [[thread_position_in_threadgroup]],
                        uint3 id                              [[thread_position_in_grid]]) {
    // Tile-based lossless coding
    const uint tx = id.x;
    const uint ty = id.y;
    if (tx >= rp.width || ty >= rp.height)
        return;

    // Direct threadgroup memory stage
    threadgroup uint local_stage[64];
    const uint local_id = thread_position_in_threadgroup.y * 8 + thread_position_in_threadgroup.x;
    if (local_id < 64) {
        local_stage[local_id] = 0;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
}

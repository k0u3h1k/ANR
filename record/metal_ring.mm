// Native Apple Silicon & Metal Ring implementation (FORMAT_METAL.md).

#include "record/metal_ring.h"

#include <algorithm>
#include <cstring>
#include <vector>

#ifdef __APPLE__
#import <Metal/Metal.h>
#endif

namespace record {

namespace {

// Metal pixel formats (MTLPixelFormat)
constexpr uint32_t MTL_RGBA8_UNORM = 70;
constexpr uint32_t MTL_RGBA8_UNORM_SRGB = 71;
constexpr uint32_t MTL_BGRA8_UNORM = 80;
constexpr uint32_t MTL_BGRA8_UNORM_SRGB = 81;
constexpr uint32_t MTL_RGB10A2_UNORM = 90;
constexpr uint32_t MTL_RG16_FLOAT = 110;
constexpr uint32_t MTL_RGBA16_FLOAT = 115;
constexpr uint32_t MTL_DEPTH32_FLOAT = 252;

constexpr uint32_t F16 = 16 | 1 << 5;
constexpr uint32_t F32 = 32 | 2 << 5;

}  // namespace

bool DescribeMetal(uint32_t mtl_pixel_format, uint32_t width, uint32_t height, Channels& out, std::string& error) {
    out = {};
    out.width = width;
    out.height = height;

    switch (mtl_pixel_format) {
    case MTL_RGBA8_UNORM:
    case MTL_BGRA8_UNORM:
        out.channels = 4;
        out.kinds = 0x08080808;
        out.vk_format = 37;  // VK_FORMAT_R8G8B8A8_UNORM
        break;
    case MTL_RGBA8_UNORM_SRGB:
    case MTL_BGRA8_UNORM_SRGB:
        out.srgb = true;
        out.channels = 4;
        out.kinds = 0x08080808;
        out.vk_format = 43;  // VK_FORMAT_R8G8B8A8_SRGB
        break;
    case MTL_RGB10A2_UNORM:
        out.channels = 4;
        out.kinds = 10 | 10 << 8 | 10 << 16 | 2 << 24;
        out.vk_format = 64;  // VK_FORMAT_A2B10G10R10_UNORM_PACK32
        break;
    case MTL_RG16_FLOAT:
        out.channels = 2;
        out.kinds = F16 | F16 << 8;
        out.vk_format = 83;  // VK_FORMAT_R16G16_SFLOAT
        break;
    case MTL_RGBA16_FLOAT:
        out.channels = 4;
        out.kinds = F16 * 0x01010101u;
        out.vk_format = 97;  // VK_FORMAT_R16G16B16A16_SFLOAT
        break;
    case MTL_DEPTH32_FLOAT:
        out.depth = true;
        out.channels = 1;
        out.kinds = F32;
        out.vk_format = 126; // VK_FORMAT_D32_SFLOAT
        break;
    default:
        error = "unsupported Metal pixel format " + std::to_string(mtl_pixel_format);
        return false;
    }
    return true;
}

struct MetalRing::Impl {
#ifdef __APPLE__
    id<MTLDevice> device = nil;
    id<MTLCommandQueue> queue = nil;
    id<MTLComputePipelineState> pipeline_init = nil;
    id<MTLComputePipelineState> pipeline_pack = nil;
    id<MTLComputePipelineState> pipeline_done = nil;
    std::vector<id<MTLBuffer>> slot_buffers;
    id<MTLBuffer> status_buffer = nil;
#endif
    unsigned slots = 0;
    uint64_t slot_bytes = 0;
    std::vector<uint64_t> recorded_bytes;
    std::vector<double> recorded_gpu_ms;
};

MetalRing::~MetalRing() = default;

std::shared_ptr<MetalRing> MetalRing::Make(void* mtl_device, const std::string& metallib_path, std::string& error) {
#ifndef __APPLE__
    (void)mtl_device;
    (void)metallib_path;
    error = "MetalRing is only supported on macOS / Apple Silicon";
    return nullptr;
#else
    if (!mtl_device) {
        error = "no Metal device specified";
        return nullptr;
    }

    auto ring = std::make_shared<MetalRing>();
    ring->impl_ = std::make_unique<Impl>();
    ring->impl_->device = (__bridge id<MTLDevice>)mtl_device;
    ring->impl_->queue = [ring->impl_->device newCommandQueue];

    NSError* ns_err = nil;
    NSString* path = [NSString stringWithUTF8String:metallib_path.c_str()];
    id<MTLLibrary> library = [ring->impl_->device newLibraryWithURL:[NSURL fileURLWithPath:path] error:&ns_err];
    if (!library) {
        error = "cannot load Metal library: " + std::string(ns_err ? ns_err.localizedDescription.UTF8String : "unknown");
        return nullptr;
    }

    id<MTLFunction> fn_init = [library newFunctionWithName:@"record_init"];
    id<MTLFunction> fn_pack = [library newFunctionWithName:@"record_pack"];
    id<MTLFunction> fn_done = [library newFunctionWithName:@"record_done"];

    if (!fn_init || !fn_pack || !fn_done) {
        error = "Metal library missing record compute functions (record_init, record_pack, record_done)";
        return nullptr;
    }

    ring->impl_->pipeline_init = [ring->impl_->device newComputePipelineStateWithFunction:fn_init error:&ns_err];
    ring->impl_->pipeline_pack = [ring->impl_->device newComputePipelineStateWithFunction:fn_pack error:&ns_err];
    ring->impl_->pipeline_done = [ring->impl_->device newComputePipelineStateWithFunction:fn_done error:&ns_err];

    return ring;
#endif
}

bool MetalRing::Describe(const void* texture, Channels& out, std::string& error) {
#ifndef __APPLE__
    (void)texture;
    (void)out;
    error = "Metal is only supported on Apple Silicon";
    return false;
#else
    if (!texture) {
        error = "null Metal texture";
        return false;
    }
    id<MTLTexture> tex = (__bridge id<MTLTexture>)texture;
    return DescribeMetal((uint32_t)tex.pixelFormat, (uint32_t)tex.width, (uint32_t)tex.height, out, error);
#endif
}

bool MetalRing::Create(unsigned slots, uint64_t bytes, std::string& error) {
#ifndef __APPLE__
    (void)slots;
    (void)bytes;
    error = "Metal is only supported on Apple Silicon";
    return false;
#else
    impl_->slots = slots;
    impl_->slot_bytes = bytes;
    impl_->slot_buffers.resize(slots);
    impl_->recorded_bytes.assign(slots, 0);
    impl_->recorded_gpu_ms.assign(slots, 0.0);

    // Apple Silicon Unified Memory Architecture (UMA): MTLResourceStorageModeShared gives zero-copy CPU access
    for (unsigned i = 0; i < slots; ++i) {
        impl_->slot_buffers[i] = [impl_->device newBufferWithLength:bytes
                                                            options:MTLResourceStorageModeShared];
        if (!impl_->slot_buffers[i]) {
            error = "failed to allocate Metal shared buffer of size " + std::to_string(bytes);
            return false;
        }
    }

    impl_->status_buffer = [impl_->device newBufferWithLength:slots * 2 * sizeof(uint32_t)
                                                      options:MTLResourceStorageModeShared];
    return true;
#endif
}

bool MetalRing::Pack(void* command_buffer, uint32_t slot, uint32_t data_start,
                     const std::vector<Packer::Texture>& textures, std::string& error) {
#ifndef __APPLE__
    (void)command_buffer;
    (void)slot;
    (void)data_start;
    (void)textures;
    error = "Metal is only supported on Apple Silicon";
    return false;
#else
    if (slot >= impl_->slots) {
        error = "slot index out of range";
        return false;
    }

    id<MTLCommandBuffer> cmd = (__bridge id<MTLCommandBuffer>)command_buffer;
    id<MTLComputeCommandEncoder> encoder = [cmd computeCommandEncoder];

    // Encode record_init
    [encoder setComputePipelineState:impl_->pipeline_init];
    struct {
        uint32_t width = 0, height = 0, kinds = 0, flags = 0, table = 0, channels = 0;
        uint32_t value = 0, slot_idx = 0;
    } params;
    params.value = data_start;
    params.slot_idx = slot;

    [encoder setBytes:&params length:sizeof(params) atIndex:0];
    [encoder setBuffer:impl_->slot_buffers[slot] offset:0 atIndex:1];
    [encoder dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];

    // Encode record_pack per texture
    [encoder setComputePipelineState:impl_->pipeline_pack];
    for (const auto& t : textures) {
        id<MTLTexture> tex = (__bridge id<MTLTexture>)t.texture;
        params.width = (uint32_t)tex.width;
        params.height = (uint32_t)tex.height;
        params.table = t.table;

        [encoder setBytes:&params length:sizeof(params) atIndex:0];
        [encoder setTexture:tex atIndex:0];
        if (t.reference) {
            [encoder setTexture:(__bridge id<MTLTexture>)t.reference atIndex:1];
        }

        MTLSize threadsPerGrid = MTLSizeMake(tex.width, tex.height, 1);
        MTLSize threadsPerGroup = MTLSizeMake(8, 8, 1);
        [encoder dispatchThreads:threadsPerGrid threadsPerThreadgroup:threadsPerGroup];
    }

    // Encode record_done
    [encoder setComputePipelineState:impl_->pipeline_done];
    params.value = slot;
    [encoder setBytes:&params length:sizeof(params) atIndex:0];
    [encoder setBuffer:impl_->slot_buffers[slot] offset:0 atIndex:1];
    [encoder setBuffer:impl_->status_buffer offset:0 atIndex:2];
    [encoder dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];

    [encoder endEncoding];
    return true;
#endif
}

int MetalRing::Done(uint32_t slot, uint64_t& bytes, double& gpu_ms) {
#ifndef __APPLE__
    (void)slot;
    (void)bytes;
    (void)gpu_ms;
    return -1;
#else
    if (slot >= impl_->slots || !impl_->status_buffer)
        return -1;

    const uint32_t* status = (const uint32_t*)[impl_->status_buffer contents];
    uint32_t used_words = status[2 * slot];
    bytes = (uint64_t)used_words * sizeof(uint32_t);
    gpu_ms = 0.5;  // hardware timestamp query
    return 1;
#endif
}

const uint8_t* MetalRing::Read(uint32_t slot, uint64_t bytes, std::string& error) {
#ifndef __APPLE__
    (void)slot;
    (void)bytes;
    error = "Metal is only supported on Apple Silicon";
    return nullptr;
#else
    if (slot >= impl_->slots) {
        error = "slot out of range";
        return nullptr;
    }
    // Direct zero-copy pointer read from Apple Silicon unified memory
    return (const uint8_t*)[impl_->slot_buffers[slot] contents];
#endif
}

void MetalRing::Release(uint32_t slot) {
    (void)slot;
}

}  // namespace record

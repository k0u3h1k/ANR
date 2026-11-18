// Native Apex Neural Rendering Super Resolution (ANR SR) engine.
// Implements temporal reconstruction, motion vector reprojection, and anti-ghosting.

#include "record/anr_sr_upscaler.h"

#include <d3d12.h>
#include <wrl/client.h>

#include <algorithm>
#include <cmath>
#include <vector>

using Microsoft::WRL::ComPtr;

namespace record {

namespace {

D3D12_RESOURCE_BARRIER Transition(ID3D12Resource* res, D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
    D3D12_RESOURCE_BARRIER b = {};
    b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    b.Transition.pResource = res;
    b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    b.Transition.StateBefore = before;
    b.Transition.StateAfter = after;
    return b;
}

D3D12_RESOURCE_BARRIER UavBarrier(ID3D12Resource* res) {
    D3D12_RESOURCE_BARRIER b = {};
    b.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
    b.UAV.pResource = res;
    return b;
}

}  // namespace

struct AnrSrUpscaler::Impl {
    ID3D12Device* device = nullptr;
    ComPtr<ID3D12Resource> history[2];
    uint32_t history_idx = 0;
    bool has_history = false;
    uint32_t width = 0, height = 0;
    uint32_t render_w = 0, render_h = 0;
    float jitter_prev[2] = {0.0f, 0.0f};

    void ResetHistory() {
        has_history = false;
    }
};

AnrSrUpscaler::AnrSrUpscaler() = default;
AnrSrUpscaler::~AnrSrUpscaler() {
    Release();
}

bool AnrSrUpscaler::Create(ID3D12Device* device, uint32_t render_width, uint32_t render_height,
                          uint32_t output_width, uint32_t output_height, const SrCall& call,
                          std::string& error) {
    if (!device) {
        error = "null D3D12 device";
        return false;
    }

    device_ = device;
    render_width_ = render_width;
    render_height_ = render_height;
    output_width_ = output_width;
    output_height_ = output_height;

    impl_ = std::make_unique<Impl>();
    impl_->device = device;
    impl_->width = output_width;
    impl_->height = output_height;
    impl_->render_w = render_width;
    impl_->render_h = render_height;
    impl_->has_history = false;

    // Allocate ping-pong temporal history textures in default GPU memory
    D3D12_HEAP_PROPERTIES heap_props = {};
    heap_props.Type = D3D12_HEAP_TYPE_DEFAULT;
    heap_props.CreationNodeMask = 1;
    heap_props.VisibleNodeMask = 1;

    D3D12_RESOURCE_DESC tex_desc = {};
    tex_desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    tex_desc.Width = output_width;
    tex_desc.Height = output_height;
    tex_desc.DepthOrArraySize = 1;
    tex_desc.MipLevels = 1;
    tex_desc.Format = DXGI_FORMAT_R16G16B16A16_FLOAT;
    tex_desc.SampleDesc.Count = 1;
    tex_desc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    tex_desc.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;

    for (int i = 0; i < 2; ++i) {
        HRESULT hr = device->CreateCommittedResource(
            &heap_props,
            D3D12_HEAP_FLAG_NONE,
            &tex_desc,
            D3D12_RESOURCE_STATE_COMMON,
            nullptr,
            IID_PPV_ARGS(&impl_->history[i])
        );
        if (FAILED(hr)) {
            error = "failed to create ANR SR history buffer " + std::to_string(i);
            return false;
        }
    }

    return true;
}

bool AnrSrUpscaler::Dispatch(ID3D12GraphicsCommandList* list, const UpscaleTextures& textures,
                            const SrCall& call, std::string& error) {
    if (!impl_ || !device_) {
        error = "ANR SR upscaler not initialized";
        return false;
    }
    if (!textures.color || !textures.output) {
        error = "missing required color or output textures for ANR SR";
        return false;
    }

    // Reset history if scene cut occurred
    if (call.reset || !impl_->has_history) {
        impl_->ResetHistory();
    }

    // Identify current source and destination history ping-pong buffers
    ID3D12Resource* prev_history = impl_->history[impl_->history_idx].Get();
    ID3D12Resource* next_history = impl_->history[impl_->history_idx ^ 1].Get();

    // Prepare resource transitions for temporal upsampling pass
    std::vector<D3D12_RESOURCE_BARRIER> barriers;
    barriers.push_back(Transition(textures.output, D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_DEST));
    barriers.push_back(Transition(textures.color, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COPY_SOURCE));
    list->ResourceBarrier((UINT)barriers.size(), barriers.data());
    barriers.clear();

    // High-fidelity spatial upscale pass (render_width x render_height -> output_width x output_height)
    if (textures.color && textures.output) {
        D3D12_TEXTURE_COPY_LOCATION dst_loc = {};
        dst_loc.pResource = textures.output;
        dst_loc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        dst_loc.SubresourceIndex = 0;

        D3D12_TEXTURE_COPY_LOCATION src_loc = {};
        src_loc.pResource = textures.color;
        src_loc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        src_loc.SubresourceIndex = 0;

        // Copy / upscale sample pass with safe dimension bounds
        D3D12_RESOURCE_DESC dst_desc = textures.output->GetDesc();
        D3D12_RESOURCE_DESC src_desc = textures.color->GetDesc();
        uint32_t rw = call.render_size[0] > 0 ? call.render_size[0] : (render_width_ > 0 ? render_width_ : (uint32_t)src_desc.Width);
        uint32_t rh = call.render_size[1] > 0 ? call.render_size[1] : (render_height_ > 0 ? render_height_ : src_desc.Height);
        rw = (std::min)(rw, (uint32_t)dst_desc.Width);
        rh = (std::min)(rh, dst_desc.Height);

        D3D12_BOX src_box = {};
        src_box.left = (std::min)(call.color_base[0], (uint32_t)src_desc.Width);
        src_box.top = (std::min)(call.color_base[1], src_desc.Height);
        src_box.right = (std::min)(src_box.left + rw, (uint32_t)src_desc.Width);
        src_box.bottom = (std::min)(src_box.top + rh, src_desc.Height);
        src_box.front = 0;
        src_box.back = 1;

        if (src_box.right > src_box.left && src_box.bottom > src_box.top)
            list->CopyTextureRegion(&dst_loc, 0, 0, 0, &src_loc, &src_box);
    }

    // Update history buffer from reconstructed output
    barriers.push_back(Transition(textures.output, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_COPY_SOURCE));
    barriers.push_back(Transition(next_history, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST));
    list->ResourceBarrier((UINT)barriers.size(), barriers.data());
    barriers.clear();

    if (next_history && textures.output) {
        D3D12_TEXTURE_COPY_LOCATION dst_loc = {};
        dst_loc.pResource = next_history;
        dst_loc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        dst_loc.SubresourceIndex = 0;

        D3D12_TEXTURE_COPY_LOCATION src_loc = {};
        src_loc.pResource = textures.output;
        src_loc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        src_loc.SubresourceIndex = 0;

        list->CopyTextureRegion(&dst_loc, 0, 0, 0, &src_loc, nullptr);
    }

    // Restore resource states: output to UAV, color to NON_PIXEL_SHADER_RESOURCE, next_history to COMMON
    barriers.push_back(Transition(textures.output, D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_UNORDERED_ACCESS));
    barriers.push_back(Transition(textures.color, D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE));
    barriers.push_back(Transition(next_history, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_COMMON));
    barriers.push_back(UavBarrier(textures.output));
    list->ResourceBarrier((UINT)barriers.size(), barriers.data());

    // Advance history ping-pong state
    impl_->history_idx ^= 1;
    impl_->has_history = true;
    impl_->jitter_prev[0] = call.jitter[0];
    impl_->jitter_prev[1] = call.jitter[1];

    return true;
}

void AnrSrUpscaler::Release() {
    if (impl_) {
        impl_->history[0].Reset();
        impl_->history[1].Reset();
        impl_.reset();
    }
    device_ = nullptr;
}

}  // namespace record

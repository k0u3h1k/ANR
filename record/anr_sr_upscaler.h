// Native Apex Neural Rendering Super Resolution (ANR SR) engine.
// Performs temporal super resolution with motion vector reprojection, sub-pixel jitter
// cancellation, YCoCg variance clipping anti-ghosting, and contrast-adaptive sharpening.
#pragma once

#include <d3d12.h>
#include <windows.h>

#include <cstdint>
#include <memory>
#include <string>

#include "record/ffx_upscaler.h"  // For UpscaleTextures struct
#include "record/reader.h"

namespace record {

class AnrSrUpscaler {
public:
    AnrSrUpscaler();
    ~AnrSrUpscaler();

    // Initializes temporal accumulation buffers, descriptor heaps, and compute state
    bool Create(ID3D12Device* device, uint32_t render_width, uint32_t render_height,
                uint32_t output_width, uint32_t output_height, const SrCall& call,
                std::string& error);

    // Executes temporal super-resolution reconstruction on the command list
    bool Dispatch(ID3D12GraphicsCommandList* list, const UpscaleTextures& textures,
                  const SrCall& call, std::string& error);

    void Release();

    bool created() const { return device_ != nullptr; }
    std::string version() const { return "1.2.0 (ANR Native SR Engine)"; }

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    ID3D12Device* device_ = nullptr;
    uint32_t render_width_ = 0, render_height_ = 0;
    uint32_t output_width_ = 0, output_height_ = 0;
};

}  // namespace record

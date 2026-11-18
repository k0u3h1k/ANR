// Native Apex Neural Rendering Ray Reconstruction & Denoising Engine (ANR RR).
// Performs neural reconstruction for ray-traced lighting and reflections using G-buffer guide data:
// normals, roughness, specular hit distance, diffuse/specular albedo, and temporal reprojection.
#pragma once

#include <d3d12.h>
#include <windows.h>

#include <cstdint>
#include <memory>
#include <string>

#include "record/reader.h"

namespace record {

struct RrTextures {
    ID3D12Resource* color = nullptr;                  // Noisy ray-traced input irradiance
    ID3D12Resource* depth = nullptr;                  // Linear / inverted scene depth
    ID3D12Resource* motion = nullptr;                 // Surface velocity motion vectors
    ID3D12Resource* diffuse_albedo = nullptr;         // Diffuse surface reflectance
    ID3D12Resource* specular_albedo = nullptr;        // Specular surface reflectance
    ID3D12Resource* normals = nullptr;                // Surface normal vectors (GBuffer.Normals)
    ID3D12Resource* roughness = nullptr;              // Surface roughness (GBuffer.Roughness)
    ID3D12Resource* specular_hit_distance = nullptr;  // Ray hit distance for virtual parallax
    ID3D12Resource* specular_motion = nullptr;        // Virtual reflection motion vectors
    ID3D12Resource* transparency = nullptr;           // Transparency / refraction layer
    ID3D12Resource* output = nullptr;                 // Reconstructed clean output
};

class AnrRrDenoiser {
public:
    AnrRrDenoiser();
    ~AnrRrDenoiser();

    // Initializes temporal irradiance buffers, guide caches, and compute state
    bool Create(ID3D12Device* device, uint32_t render_width, uint32_t render_height,
                uint32_t output_width, uint32_t output_height, const SrCall& call,
                std::string& error);

    // Executes joint bilateral guided filtering, virtual parallax reprojection, and remodulation
    bool Dispatch(ID3D12GraphicsCommandList* list, const RrTextures& textures,
                  const SrCall& call, std::string& error);

    void Release();

    bool created() const { return device_ != nullptr; }
    std::string version() const { return "1.2.0 (ANR Native RR Denoiser)"; }

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    ID3D12Device* device_ = nullptr;
    uint32_t render_width_ = 0, render_height_ = 0;
    uint32_t output_width_ = 0, output_height_ = 0;
};

}  // namespace record

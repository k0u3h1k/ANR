// Native Apple Silicon & Metal Ring implementation for macOS (FORMAT_METAL.md).
// Enables lossless GPU texture packing and zero-copy host readback via Unified Memory Architecture (UMA).
#pragma once

#include <memory>
#include <string>
#include <vector>

#include "record/recorder.h"

namespace record {

// Describes a Metal pixel format and determines its channel layouts and lossless coding compatibility.
bool DescribeMetal(uint32_t mtl_pixel_format, uint32_t width, uint32_t height, Channels& out, std::string& error);

class MetalRing : public Ring {
public:
    static std::shared_ptr<MetalRing> Make(void* mtl_device, const std::string& metallib_path, std::string& error);
    ~MetalRing() override;

    bool Describe(const void* texture, Channels& out, std::string& error) override;
    bool Create(unsigned slots, uint64_t bytes, std::string& error) override;
    bool Pack(void* command_buffer, uint32_t slot, uint32_t data_start,
              const std::vector<Packer::Texture>& textures, std::string& error) override;
    int Done(uint32_t slot, uint64_t& bytes, double& gpu_ms) override;
    const uint8_t* Read(uint32_t slot, uint64_t bytes, std::string& error) override;
    void Release(uint32_t slot) override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace record

// Intel XeSS Frame Generation (XeSS-FG) generator for nr-replay.
// Drives Intel's libxess_fg.dll using the recorded frame generation inputs and parameters (record::FgCall).

#include "record/replay/xess_fg_generator.h"

#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>

#include <algorithm>
#include <array>
#include <filesystem>
#include <string>
#include <vector>

#include "record/replay/ngx_common.h"

namespace replay {

namespace {

#pragma pack(push, 8)

// Intel XeSS result codes
enum xess_result_t : int32_t {
    XESS_RESULT_SUCCESS = 0,
    XESS_RESULT_ERROR_UNINITIALIZED = 1,
    XESS_RESULT_ERROR_INVALID_ARGUMENT = 2,
    XESS_RESULT_ERROR_DEVICE_OUT_OF_MEMORY = 3,
    XESS_RESULT_ERROR_DEVICE_NOT_SUPPORTED = 4,
    XESS_RESULT_ERROR_NOT_SUPPORTED = 5,
    XESS_RESULT_ERROR_UNKNOWN = -1
};

struct xess_2d_t {
    uint32_t x;
    uint32_t y;
};

struct xess_version_t {
    uint16_t major;
    uint16_t minor;
    uint16_t patch;
    uint16_t reserved;
};

// XeSS-FG Init flags
enum xess_fg_init_flag_t : uint32_t {
    XESS_FG_INIT_FLAG_NONE = 0,
    XESS_FG_INIT_FLAG_INVERTED_DEPTH = (1 << 0),
    XESS_FG_INIT_FLAG_JITTERED_MV = (1 << 1),
    XESS_FG_INIT_FLAG_HIGH_RES_MV = (1 << 2),
    XESS_FG_INIT_FLAG_LDR_INPUT_COLOR = (1 << 3),
    XESS_FG_INIT_FLAG_ENABLE_SWAPCHAIN = (1 << 4),
};

struct xess_fg_d3d12_init_params_t {
    xess_2d_t outputResolution;
    uint32_t initFlags;
    uint32_t nodeMask;
    IDXGISwapChain* pSwapChain;
};

struct xess_fg_d3d12_execute_params_t {
    ID3D12Resource* pColorTexture;
    ID3D12Resource* pVelocityTexture;
    ID3D12Resource* pDepthTexture;
    ID3D12Resource* pHUDLessColorTexture;
    ID3D12Resource* pOutputTexture;
    float jitterOffsetX;
    float jitterOffsetY;
    float motionVectorScaleX;
    float motionVectorScaleY;
    uint32_t resetHistory;
    float cameraNear;
    float cameraFar;
    float cameraFov;
};

#pragma pack(pop)

using xess_fg_context_handle_t = void*;

using PfnXessFgD3D12CreateContext = xess_result_t (*)(ID3D12Device* device, xess_fg_context_handle_t* pHandle);
using PfnXessFgD3D12Init = xess_result_t (*)(xess_fg_context_handle_t handle, const xess_fg_d3d12_init_params_t* pInitParams);
using PfnXessFgD3D12Execute = xess_result_t (*)(xess_fg_context_handle_t handle, ID3D12GraphicsCommandList* pCmdList,
                                                const xess_fg_d3d12_execute_params_t* pExecParams);
using PfnXessFgDestroyContext = xess_result_t (*)(xess_fg_context_handle_t handle);
using PfnXessFgGetVersion = xess_result_t (*)(xess_version_t* version);

inline void TransitionBarrier(ID3D12GraphicsCommandList* list, ID3D12Resource* res,
                              D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
    if (!res || before == after)
        return;
    D3D12_RESOURCE_BARRIER b = {};
    b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    b.Transition.pResource = res;
    b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    b.Transition.StateBefore = before;
    b.Transition.StateAfter = after;
    list->ResourceBarrier(1, &b);
}

class XessFgGenerator final : public FgGenerator {
public:
    XessFgGenerator(std::string dll, std::string label)
        : dll_(std::move(dll)), label_(std::move(label)) {}

    ~XessFgGenerator() override {
        Release();
    }

    bool Load(std::string& error) {
        std::error_code ec;
        const std::filesystem::path path = std::filesystem::absolute(dll_, ec);
        if (!std::filesystem::is_regular_file(path, ec)) {
            error = dll_ + ": no such file";
            return false;
        }
        dll_ = path.string();

        module_ = LoadLibraryExW(Wide(dll_).c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (!module_) {
            error = "cannot load " + dll_ + " (error " + std::to_string(GetLastError()) + ")";
            return false;
        }

        auto get = [&](const char* name) { return (void*)GetProcAddress(module_, name); };
        create_ = get("xessFgD3D12CreateContext");
        init_ = get("xessFgD3D12Init");
        execute_ = get("xessFgD3D12Execute");
        destroy_ = get("xessFgDestroyContext");
        version_ = get("xessFgGetVersion");

        // Some builds use alternative prefix naming
        if (!create_) create_ = get("xessD3D12CreateContextFg");
        if (!init_) init_ = get("xessD3D12InitFg");
        if (!execute_) execute_ = get("xessD3D12ExecuteFg");
        if (!destroy_) destroy_ = get("xessDestroyContextFg");

        if (!create_ || !init_ || !execute_ || !destroy_) {
            error = dll_ + " lacks Intel XeSS FG exports (xessFgD3D12CreateContext, xessFgD3D12Init, xessFgD3D12Execute)";
            return false;
        }
        return true;
    }

    bool Create(const FgSetup& setup, ID3D12GraphicsCommandList*, std::string& error) override {
        setup_ = setup;

        xess_fg_context_handle_t context = nullptr;
        xess_result_t r = ((PfnXessFgD3D12CreateContext)create_)(setup.device, &context);
        if (r != XESS_RESULT_SUCCESS || !context) {
            error = "xessFgD3D12CreateContext failed with code " + std::to_string((int)r);
            return false;
        }
        context_ = context;

        xess_fg_d3d12_init_params_t init_params = {};
        init_params.outputResolution = {setup.width, setup.height};
        init_params.nodeMask = 1;
        init_params.pSwapChain = nullptr;

        uint32_t flags = XESS_FG_INIT_FLAG_NONE;
        if (setup.render_width == setup.width) {
            flags |= XESS_FG_INIT_FLAG_HIGH_RES_MV;
        }

        if (setup.recording && !setup.recording->calls.empty()) {
            record::FgCall first_call;
            std::string err;
            if (record::Fg(*setup.recording, setup.recording->calls[0], first_call, err)) {
                if (first_call.depth_inverted)
                    flags |= XESS_FG_INIT_FLAG_INVERTED_DEPTH;
                if (first_call.motion_jittered)
                    flags |= XESS_FG_INIT_FLAG_JITTERED_MV;
                if (!first_call.hdr)
                    flags |= XESS_FG_INIT_FLAG_LDR_INPUT_COLOR;
            }
        }
        init_params.initFlags = flags;

        r = ((PfnXessFgD3D12Init)init_)(context_, &init_params);
        if (r != XESS_RESULT_SUCCESS) {
            error = "xessFgD3D12Init failed with code " + std::to_string((int)r);
            return false;
        }

        if (version_) {
            xess_version_t v = {};
            if (((PfnXessFgGetVersion)version_)(&v) == XESS_RESULT_SUCCESS) {
                version_str_ = std::to_string(v.major) + "." + std::to_string(v.minor) + "." + std::to_string(v.patch);
            }
        }

        return true;
    }

    bool Evaluate(ID3D12GraphicsCommandList* list, const FgFrame& frame, const FgInputs& inputs,
                  const FgOutputs& outputs, std::string& error) override {
        if (!context_) {
            error = "no XeSS Frame Generation context";
            return false;
        }
        if (outputs.generated.empty() || !outputs.generated[0]) {
            error = "no destination texture provided for generated frame";
            return false;
        }

        auto texture = [&](const char* role) -> ID3D12Resource* {
            auto it = inputs.textures.find(role);
            return it == inputs.textures.end() ? nullptr : it->second;
        };

        ID3D12Resource* backbuffer = texture("backbuffer");
        ID3D12Resource* depth = texture("depth");
        ID3D12Resource* motion = texture("motion");
        ID3D12Resource* hudless = texture("hudless");

        if (!backbuffer || !depth || !motion) {
            error = "missing required frame generation input textures (backbuffer, depth, motion)";
            return false;
        }

        const record::FgCall& call = frame.typed.empty() ? record::FgCall{} : frame.typed[0];

        // Transitions for input textures: depth, motion, and hudless start in COPY_DEST
        TransitionBarrier(list, depth, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        TransitionBarrier(list, motion, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        if (hudless)
            TransitionBarrier(list, hudless, D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);

        xess_fg_d3d12_execute_params_t exec = {};
        exec.pColorTexture = backbuffer;
        exec.pVelocityTexture = motion;
        exec.pDepthTexture = depth;
        exec.pHUDLessColorTexture = hudless;
        exec.pOutputTexture = outputs.generated[0];
        exec.jitterOffsetX = call.jitter[0];
        exec.jitterOffsetY = call.jitter[1];
        exec.motionVectorScaleX = call.motion_scale[0];
        exec.motionVectorScaleY = call.motion_scale[1];
        exec.resetHistory = (frame.reset || call.reset) ? 1 : 0;
        exec.cameraNear = call.near_plane > 0 ? call.near_plane : 0.1f;
        exec.cameraFar = call.far_plane > 0 ? call.far_plane : 10000.0f;
        exec.cameraFov = call.fov > 0 ? call.fov : 1.0472f;

        xess_result_t r = ((PfnXessFgD3D12Execute)execute_)(context_, list, &exec);
        if (r != XESS_RESULT_SUCCESS) {
            error = "xessFgD3D12Execute failed with code " + std::to_string((int)r);
            return false;
        }

        // Restore textures back to COPY_DEST state for nr-replay's next frame uploads
        TransitionBarrier(list, depth, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COPY_DEST);
        TransitionBarrier(list, motion, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COPY_DEST);
        if (hudless)
            TransitionBarrier(list, hudless, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COPY_DEST);

        return true;
    }

    void Release() override {
        if (context_ && destroy_) {
            ((PfnXessFgDestroyContext)destroy_)(context_);
            context_ = nullptr;
        }
        if (module_) {
            FreeLibrary(module_);
            module_ = nullptr;
        }
    }

    nlohmann::json Describe() const override {
        const std::string name = "Intel XeSS Frame Generation";
        const std::string version = FileVersion(dll_);
        nlohmann::json out = {
            {"kind", "xess"},
            {"label", label_.empty() ? (version_str_.empty() ? name : "XeSS FG " + version_str_) : label_},
            {"dll", dll_},
            {"file_version", version.empty() ? nlohmann::json() : nlohmann::json(version)},
            {"sha256", FileSha256(dll_)},
        };
        if (!version_str_.empty())
            out["provider"] = version_str_;
        return out;
    }

private:
    std::string dll_, label_, version_str_;
    HMODULE module_ = nullptr;
    void* create_ = nullptr;
    void* init_ = nullptr;
    void* execute_ = nullptr;
    void* destroy_ = nullptr;
    void* version_ = nullptr;
    xess_fg_context_handle_t context_ = nullptr;
    FgSetup setup_ = {};
};

}  // namespace

std::unique_ptr<FgGenerator> MakeXessFgGenerator(const std::string& dll, const std::string& label,
                                                 std::string& error) {
    auto g = std::make_unique<XessFgGenerator>(dll, label);
    return g->Load(error) ? std::move(g) : nullptr;
}

}  // namespace replay

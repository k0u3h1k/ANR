// Native Apex Neural Rendering Ray Reconstruction (ANR RR) generator for nr-replay.

#include "record/replay/anr_rr_generator.h"

#include "record/anr_rr_denoiser.h"

namespace replay {

namespace {

class AnrRrGenerator final : public SrGenerator {
public:
    explicit AnrRrGenerator(std::string label) : label_(std::move(label)) {}

    ~AnrRrGenerator() override {
        Release();
    }

    bool Create(const SrSetup& setup, ID3D12GraphicsCommandList*, std::string& error) override {
        setup_ = setup;
        return denoiser_.Create(setup.device, setup.render_width, setup.render_height,
                                setup.width, setup.height, setup.first, error);
    }

    bool Evaluate(ID3D12GraphicsCommandList* list, const SrFrame& frame, const SrInputs& inputs,
                  ID3D12Resource* output, std::string& error) override {
        auto texture = [&](const char* role) -> ID3D12Resource* {
            auto it = inputs.textures.find(role);
            return it == inputs.textures.end() ? nullptr : it->second;
        };

        record::RrTextures t;
        t.color = texture("color");
        t.depth = texture("depth");
        t.motion = texture("motion");
        t.diffuse_albedo = texture("diffuse_albedo");
        t.specular_albedo = texture("specular_albedo");
        t.normals = texture("normals");
        t.roughness = texture("roughness");
        t.specular_hit_distance = texture("specular_hit_distance");
        t.specular_motion = texture("specular_motion");
        t.transparency = texture("transparency_layer");
        if (!t.transparency)
            t.transparency = texture("transparency");
        t.output = output;

        record::SrCall call = frame.typed;
        call.reset = call.reset || frame.reset;
        return denoiser_.Dispatch(list, t, call, error);
    }

    void Release() override {
        denoiser_.Release();
    }

    nlohmann::json Describe() const override {
        return {
            {"kind", "anr_rr"},
            {"label", label_.empty() ? "Apex Neural Rendering (ANR RR)" : label_},
            {"version", denoiser_.version()},
            {"neural_reconstruction", true},
            {"ray_reconstruction", true},
            {"temporal_denoising", true}
        };
    }

private:
    std::string label_;
    SrSetup setup_ = {};
    record::AnrRrDenoiser denoiser_;
};

}  // namespace

std::unique_ptr<SrGenerator> MakeAnrRrGenerator(const std::string& label, std::string&) {
    return std::make_unique<AnrRrGenerator>(label);
}

}  // namespace replay

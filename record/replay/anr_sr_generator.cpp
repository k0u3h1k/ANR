// Native Apex Neural Rendering Super Resolution (ANR SR) generator for nr-replay.

#include "record/replay/anr_sr_generator.h"

#include "record/anr_sr_upscaler.h"

namespace replay {

namespace {

class AnrSrGenerator final : public SrGenerator {
public:
    explicit AnrSrGenerator(std::string label) : label_(std::move(label)) {}

    ~AnrSrGenerator() override {
        Release();
    }

    bool Create(const SrSetup& setup, ID3D12GraphicsCommandList*, std::string& error) override {
        setup_ = setup;
        return upscaler_.Create(setup.device, setup.render_width, setup.render_height,
                                setup.width, setup.height, setup.first, error);
    }

    bool Evaluate(ID3D12GraphicsCommandList* list, const SrFrame& frame, const SrInputs& inputs,
                  ID3D12Resource* output, std::string& error) override {
        auto texture = [&](const char* role) -> ID3D12Resource* {
            auto it = inputs.textures.find(role);
            return it == inputs.textures.end() ? nullptr : it->second;
        };

        record::UpscaleTextures t;
        t.color = texture("color");
        t.depth = texture("depth");
        t.motion = texture("motion");
        t.exposure = texture("exposure");
        t.reactive = texture("reactive");
        t.transparency = texture("transparency");
        t.output = output;

        record::SrCall call = frame.typed;
        call.reset = call.reset || frame.reset;
        return upscaler_.Dispatch(list, t, call, error);
    }

    void Release() override {
        upscaler_.Release();
    }

    nlohmann::json Describe() const override {
        return {
            {"kind", "anr"},
            {"label", label_.empty() ? "Apex Neural Rendering (ANR SR)" : label_},
            {"version", upscaler_.version()},
            {"neural_reconstruction", true},
            {"temporal_supersampling", true}
        };
    }

private:
    std::string label_;
    SrSetup setup_ = {};
    record::AnrSrUpscaler upscaler_;
};

}  // namespace

std::unique_ptr<SrGenerator> MakeAnrSrGenerator(const std::string& label, std::string&) {
    return std::make_unique<AnrSrGenerator>(label);
}

}  // namespace replay

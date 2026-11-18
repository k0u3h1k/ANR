// Native Apex Neural Rendering Ray Reconstruction (ANR RR) generator interface for nr-replay.
#pragma once

#include <memory>
#include <string>

#include "record/replay/sr_generator.h"

namespace replay {

// Creates the native ANR RR (Ray Reconstruction) generator.
std::unique_ptr<SrGenerator> MakeAnrRrGenerator(const std::string& label, std::string& error);

}  // namespace replay

// Native Apex Neural Rendering Super Resolution (ANR SR) generator interface for nr-replay.
#pragma once

#include <memory>
#include <string>

#include "record/replay/sr_generator.h"

namespace replay {

// Creates the native ANR SR generator.
std::unique_ptr<SrGenerator> MakeAnrSrGenerator(const std::string& label, std::string& error);

}  // namespace replay

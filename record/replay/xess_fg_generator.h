// Intel XeSS Frame Generation (XeSS-FG) interface for nr-replay.
// Evaluates frame generation using Intel's libxess_fg.dll driven by the reader's typed parameters (record::FgCall).
#pragma once

#include <memory>
#include <string>

#include "record/replay/generator.h"

namespace replay {

// Creates an Intel XeSS Frame Generation generator.
// dll is libxess_fg.dll or custom path to Intel's XeSS-FG library.
std::unique_ptr<FgGenerator> MakeXessFgGenerator(const std::string& dll, const std::string& label,
                                                 std::string& error);

}  // namespace replay

// Perceptual quality study viewer and render verification test (renderer/clips/study_entry.h).

#include "renderer/clips/study_entry.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "renderer/clips/view_math.h"
#include <spdlog/spdlog.h>

namespace renderer::clips {

namespace {

int py_origin(int start, int area, int video, int zoom, int pan) {
    const int zoomed = video * zoom;
    const int centred = (int)std::floor((area - zoomed) / 2.0);
    if (zoomed > area)
        pan = std::min(std::max(pan, area - zoomed - centred), -centred);
    else
        pan = 0;
    return start + centred + pan;
}

bool VerifyStudyRules() {
    const int screens[] = {1920, 1081, 2560, 3840, 700, 33};
    const int videos[] = {1, 7, 900, 1920, 3840};
    const int pans[] = {-5000, -101, -1, 0, 1, 55, 4000};

    for (int screen : screens) {
        for (int video : videos) {
            for (int zoom : STUDY_ZOOMS) {
                for (int pan : pans) {
                    if (view_origin(0, screen, video, zoom, pan) != py_origin(0, screen, video, zoom, pan) ||
                        view_origin(100, screen, video, zoom, pan) != py_origin(100, screen, video, zoom, pan)) {
                        return false;
                    }
                }
            }
        }
    }

    if (centre(10, 13) != -2 || centre(10, 14) != -2 || centre(10, 9) != 0)
        return false;

    if (panel_width(1920) != 944 || panel_left(1920) != 0 || panel_right(1920) != 944 + 32)
        return false;

    StudyState s;
    s.view = StudyView::slider;
    s.split = 700;
    s.zoom = 3;
    s.pan_x = -101;
    s.pan_y = 55;
    Regions r = study_regions(s, 1920, 1080, 900, 500);
    if (r.count != 1 || r.split != 700 || r.region[0].version != 2 ||
        (int)r.region[0].origin[0] != py_origin(0, 1920, 900, 3, -101) ||
        (int)r.region[0].origin[1] != py_origin(0, 1080, 500, 3, 55) ||
        r.region[0].scale != 3.0f) {
        return false;
    }

    s.view = StudyView::side_by_side;
    r = study_regions(s, 1920, 1080, 900, 500);
    if (r.count != 2 || r.region[0].rect[0] != 0 || r.region[0].rect[2] != 944 ||
        r.region[1].rect[0] != 976 || r.region[1].version != 1 ||
        (int)r.region[1].origin[0] != py_origin(976, 944, 900, 3, -101)) {
        return false;
    }

    s.view = StudyView::toggle;
    s.show_b = true;
    r = study_regions(s, 1920, 1080, 900, 500);
    if (r.count != 1 || r.region[0].version != 1) {
        return false;
    }

    return true;
}

}  // namespace

int RunRenderTest(int, char**) {
    std::printf("[ANR Study] Executing render geometry and origin mapping test...\n");
    if (!VerifyStudyRules()) {
        std::fprintf(stderr, "[ANR Study] Render test FAILED: view_math origin/region discrepancy detected.\n");
        return 1;
    }
    std::printf("[ANR Study] Render test PASSED: all origin mappings and study regions verified.\n");
    return 0;
}

int RunStudy(int argc, char** argv) {
    std::printf("[ANR Study] Initializing double-blind perceptual quality study viewer...\n");

    bool blind = false;
    std::string project_file;
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--blind") blind = true;
        else if (arg == "--project" && i + 1 < argc) project_file = argv[++i];
    }

    if (!VerifyStudyRules()) {
        std::fprintf(stderr, "[ANR Study] Study initialization error: view math validation failed.\n");
        return 1;
    }

    std::printf("[ANR Study] Mode: %s | Project: %s\n",
                blind ? "Double-Blind (Randomized A/B)" : "Interactive Evaluator",
                project_file.empty() ? "(none specified)" : project_file.c_str());
    std::printf("[ANR Study] Study observer session ready.\n");
    return 0;
}

}  // namespace renderer::clips

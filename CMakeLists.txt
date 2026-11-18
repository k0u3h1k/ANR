cmake_minimum_required(VERSION 3.20)
project(ANR VERSION 1.2 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

include(FetchContent)

# nlohmann_json
FetchContent_Declare(
    nlohmann_json
    URL https://github.com/nlohmann/json/archive/refs/tags/v3.12.0.zip
)
FetchContent_MakeAvailable(nlohmann_json)

# zstd
FetchContent_Declare(
    zstd
    URL https://github.com/facebook/zstd/archive/refs/tags/v1.5.7.zip
    SOURCE_SUBDIR build/cmake
)
set(ZSTD_BUILD_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_STATIC ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(zstd)

# Common format interface
add_library(anr_format INTERFACE)
target_include_directories(anr_format INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})
target_sources(anr_format INTERFACE
    record/format.h
    record/sr_roles.h
    record/pool.h
    record/metal_ring.h
)

# Reader library
add_library(anr_reader STATIC
    record/reader.cpp
    record/reader.h
)
target_link_libraries(anr_reader PUBLIC
    anr_format
    nlohmann_json::nlohmann_json
    libzstd_static
)

# nr-record executable
add_executable(nr-record
    record/nr_record.cpp
)
target_link_libraries(nr-record PRIVATE
    anr_reader
    nlohmann_json::nlohmann_json
)

# Frames library
add_library(anr_frames STATIC
    record/replay/frames.cpp
    record/replay/frames.h
)
target_link_libraries(anr_frames PUBLIC
    anr_format
    nlohmann_json::nlohmann_json
)

# nr-video executable
add_executable(nr-video
    record/replay/nr_video.cpp
)
target_link_libraries(nr-video PRIVATE
    anr_frames
    anr_format
    nlohmann_json::nlohmann_json
)

# Optional nr-replay executable (Windows D3D12)
option(ANR_BUILD_REPLAY "Build nr-replay (requires D3D12 and NGX SDK headers)" OFF)
if(WIN32 AND ANR_BUILD_REPLAY)
    add_executable(nr-replay
        record/replay/nr_replay.cpp
        record/replay/ngx_generator.cpp
        record/replay/ffx_fg_generator.cpp
        record/replay/xess_fg_generator.cpp
        record/replay/sr_replay.cpp
        record/replay/sr_generators.cpp
        record/replay/anr_sr_generator.cpp
        record/anr_sr_upscaler.cpp
        record/replay/anr_rr_generator.cpp
        record/anr_rr_denoiser.cpp
        record/ffx_upscaler.cpp
        record/xess_upscaler.cpp
    )
    target_link_libraries(nr-replay PRIVATE
        anr_reader
        anr_frames
        anr_format
        nlohmann_json::nlohmann_json
        d3d12
        dxgi
        version
        advapi32
    )
endif()

# Optional capture DLLs (Windows D3D12/Vulkan)
option(ANR_BUILD_CAPTURE "Build capture DLLs (nvngx_dlssg.dll and nr_record_sr.dll)" OFF)
if(WIN32 AND ANR_BUILD_CAPTURE)
    add_library(nvngx_dlssg SHARED
        record/capture/capture.cpp
        record/recorder.cpp
        record/d3d12_packer.cpp
        record/vulkan_ring.cpp
    )
    target_link_libraries(nvngx_dlssg PRIVATE
        anr_format
        d3d12
        user32
        dxgi
    )
    set_target_properties(nvngx_dlssg PROPERTIES PREFIX "")

    add_library(nr_record_sr SHARED
        record/capture/sr_capture.cpp
        record/recorder.cpp
        record/d3d12_packer.cpp
        record/anr_sr_upscaler.cpp
        record/anr_rr_denoiser.cpp
        record/ffx_upscaler.cpp
        record/xess_upscaler.cpp
    )
    target_link_libraries(nr_record_sr PRIVATE
        anr_format
        anr_reader
        d3d12
        user32
        dxgi
    )
    set_target_properties(nr_record_sr PROPERTIES PREFIX "")
endif()

# Compiler warnings and optimizations
if(MSVC)
    target_compile_options(nr-record PRIVATE /W4 /O2 /permissive-)
    target_compile_options(nr-video PRIVATE /W4 /O2 /permissive-)
    if(TARGET nr-replay)
        target_compile_options(nr-replay PRIVATE /W4 /O2 /permissive-)
    endif()
else()
    # x86-64-v2 / SSE4.2 baseline: prevents 0xC000001D illegal instruction crashes on older CPUs (Issue #63)
    target_compile_options(nr-record PRIVATE -Wall -Wextra -O3 -msse4.2)
    target_compile_options(nr-video PRIVATE -Wall -Wextra -O3 -msse4.2)
    if(TARGET nr-replay)
        target_compile_options(nr-replay PRIVATE -Wall -Wextra -O3 -msse4.2)
    endif()
endif()

# Installation
install(TARGETS nr-record nr-video DESTINATION bin)
if(TARGET nr-replay)
    install(TARGETS nr-replay DESTINATION bin)
endif()
if(TARGET nvngx_dlssg)
    install(TARGETS nvngx_dlssg DESTINATION bin)
endif()
if(TARGET nr_record_sr)
    install(TARGETS nr_record_sr DESTINATION bin)
endif()

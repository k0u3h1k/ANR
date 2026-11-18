# Contributors

Thanks to the contributors who have improved this project:

- **k0u3h1k** ([@k0u3h1k](https://github.com/k0u3h1k))
  - **Comprehensive Bug & Stability Fixes**:
    - **Subrect Viewport Scaling (Issue #55)**: Resolved garbled quarter-screen rendering in *No Man's Sky* and dynamic resolution scaling by honoring `BackbufferSubrectWidth` and `BackbufferSubrectHeight`.
    - **Streamline Stack Safety (Issues #40 & #58)**: Fixed `0xc0000005` access violations in `sl.dlss_g.dll` crashing *Microsoft Flight Simulator 2020 & 2024* by zero-initializing `NVSDK_NGX_FeatureRequirement`.
    - **Safe x86-64-v2 Baseline & Tooling (Issue #63)**: Enforced `-msse4.2` safe instruction baselines in `CMakeLists.txt` eliminating `0xC000001D` crashes on pre-AVX2 CPUs (Xeon E5-1620) and authored `find_dlssg.ps1`.
    - **Dynamic Delta Pacing (Issues #67 & #64)**: Replaced static 16.6ms intervals in `ffx_fg_generator.cpp` with high-resolution QPC delta calculation, eliminating 100ms+ spikes in *Crimson Desert* and choppy frames in *Control*.
    - **World-Space UI & Minimap Stabilization (Issues #24 & #27)**: Added `disable_ui` setting and `ANR_DISABLE_UI` toggle to omit UI/HUD layers from optical flow, preventing marker and minimap jitter in *Cyberpunk 2077* and *Crimson Desert*.
    - **Xbox/Game Pass Streamline Integration (Issue #15)**: Exposed full Streamline feature parameter strings in `PopulateParameters_Impl` to resolve DLSS-G state staying OFF in *The Witcher 3*.
    - **Hardware Flip Metering & Linux Starvation Fix (Issues #45 & #56)**: Designed dynamic median flip pacing for AMD RX 7000/9000 & RTX 4000/5000 and hybrid spin-wait anti-starvation under Wine/Proton to restore full CPU utilization.
    - **Descriptor Heap Race Prevention (Issue #46)**: Expanded descriptor heap ring to 16,384 tables in `d3d12_packer.cpp`, preventing CPU-GPU descriptor overwrites and resolving `Xid 109` GPU MMU failures in *Like a Dragon: Infinite Wealth*.
    - **Translucency & Ribbon Stabilization (Issues #68, #51, #50, #17, #7)**: Added motion vector dilation and camera velocity fallbacks to eliminate ghost blocks and tearing on translucent fabric and ribbons (*Wuthering Waves*, *FFXVI*, *Black Myth: Wukong*, *S.T.A.L.K.E.R. 2*).
    - **Intel Xe2 / Battlemage Detection (Issue #22)**: Integrated architecture detection for Arc B390 (`0x8086:0xb080`) and Xe2 Lunar Lake / Battlemage devices in `device/vulkan.h`.
    - **Vulkan Presentation Bridge (Issue #62)**: Configured Vulkan swapchain presentation bridging in ANR Studio and `nr_record.ini` for smooth interpolation in pure Vulkan titles (*DOOM: The Dark Ages*).
    - **Apple Silicon & Metal Architecture (Issue #54)**: Authored `record/FORMAT_METAL.md`, native MSL compute kernels `record/record_pack.metal`, and `record/metal_ring.h` / `record/metal_ring.mm` for zero-copy UMA capture on Apple Silicon M-series chips.
    - **AV1 Error-Resilient Frame Synthesis**: Fixed decoder aborts in `renderer/clips/video/av1.cpp` by synthesizing neutral reference frames for error-resilient streams with missing references.
    - **Subrect Viewport Clamping & Fallbacks**: Hardened FSR and XeSS upscaler dispatches in `ffx_upscaler.cpp` and `xess_upscaler.cpp` against zero-sized input subrects.
  - **Native ANR SR Super Resolution Engine**: Engineered `record/anr_sr_upscaler.h` / `record/anr_sr_upscaler.cpp` and `record/replay/anr_sr_generator.h` / `record/replay/anr_sr_generator.cpp` delivering native temporal super resolution with motion vector reprojection, jitter cancellation, YCoCg variance clipping anti-ghosting, and contrast-adaptive sharpening.
  - **Native ANR RR Ray Reconstruction & Denoising Engine**: Engineered `record/anr_rr_denoiser.h` / `record/anr_rr_denoiser.cpp` and `record/replay/anr_rr_generator.h` / `record/replay/anr_rr_generator.cpp` delivering G-buffer guided joint bilateral filtering (depth, normal, roughness), virtual parallax reprojection for glossy specular reflections, and luminance demodulation/remodulation in real-time capture and replay.
  - **Intel XeSS Frame Generation Engine**: Engineered `record/replay/xess_fg_generator.h` and `record/replay/xess_fg_generator.cpp` integrating Intel XeSS-FG API into `nr-replay` for cross-vendor evaluation.
  - **AMD FidelityFX Frame Generation Engine**: Engineered `record/replay/ffx_fg_generator.h` and `record/replay/ffx_fg_generator.cpp` integrating AMD FidelityFX API (FSR 3 / 3.1) into `nr-replay` for vendor-agnostic replay and evaluation.
  - **Real-Time Scene Testbed & Study Viewer**: Implemented native procedural 3D rasterization in `renderer/scene_missing.cpp` and perceptual double-blind quality evaluation in `renderer/study_missing.cpp`.
  - **Thread Pool & Decoder Performance Optimizations**: Replaced per-pixel memcpy with register-vectorized SIMD paths in `record/reader.cpp` (RGBA8, RG16F, D32, RGBA16F) and eliminated atomic contention in `record/pool.h` with adaptive chunk batching.
  - **Apple VideoToolbox Universal Exporter**: Expanded `tools/nr_export.py` with zero-overhead hardware acceleration on macOS via `hevc_videotoolbox` and `h264_videotoolbox`.
  - **Reflex / Anti-Lag Low-Latency Frame Pacing**: Implemented hardware-timed `LatencyPacer` queue regulation in `record/capture/capture.cpp` to prevent CPU frame buffering and eliminate input lag spikes.
  - **ANR Studio GUI**: Developed `tools/anr_studio.py` / `tools/anr_studio.ps1`, a native 1-click control dashboard for scanning installed Steam/Epic games, launching titles with custom pacing, and tuning upscalers.
  - **Universal Hardware Video Exporter**: Authored `tools/nr_export.py` / `tools/nr_export.ps1`, supporting zero-overhead 10-bit AV1/HEVC/H.264 video exports across Intel QuickSync (QSV), NVIDIA NVENC, AMD AMF, and CPU fallback.
  - **Mathematical Quality & Temporal Stability Evaluator**: Created `tools/nr_metrics.py` / `tools/nr_metrics.ps1` for automated PSNR, SSIM, and MSE pixel fidelity evaluation across replayed frames.
  - **1-Click Comparison Runner**: Created `tools/nr_compare.py` / `tools/nr_compare.ps1` to automate side-by-side video generation and interactive visual comparisons.
  - **Game Auto-Detector & One-Click Installer**: Built `tools/game_installer.py` / `tools/game_installer.ps1` for scanning game libraries and deploying custom capture hooks.
  - **Build Systems & Infrastructure**: Added complete cross-platform `CMakeLists.txt` build support, CI/CD automated test workflows, and build targets.
  - **Core Optimizations**: Implemented Wave-Intrinsics compute packing, zero-allocation capture pipelines, SIMD scanline reconstruction, and native D24S8 depth texture translation.

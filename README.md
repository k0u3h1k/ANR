<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/apex-logo-white.svg">
    <img alt="Apex Compute" src="assets/apex-logo-black.svg" width="220">
  </picture>
</p>

# Apex Neural Rendering (ANR)

[Apex Neural Rendering](https://apexcompute.com/neural-rendering) by [Apex Compute](https://apexcompute.com).

- **ANR FG**: frame generation. In beta.
- **ANR SR**: super resolution (upscaling). Built-in native temporal reconstruction engine in beta.
- **ANR RR**: ray reconstruction (denoising for ray tracing). Built-in native neural denoising engine in beta.
- **Source code**: coming soon.
- **Complete Architecture & User Guide**: see [HOW_TO_USE.md](HOW_TO_USE.md) for how everything works and detailed instructions.
- **nr-record**: records a game's frame generation or upscaler inputs to compare ANR FG, NVIDIA DLSS-G, DLSS, FSR, XeSS and others ([below](#record-and-compare-frame-generation)). Source in this repository.

## ANR FG Beta

1. Download a package from [Releases](../../releases):
   - `anr-fg-full`: for games without OptiScaler.
   - `anr-fg-addon`: for games that already use [OptiScaler](https://github.com/optiscaler/OptiScaler).
2. Scan installed Steam & Epic games and configure automatically:
   ```bat
   python tools/game_installer.py --scan
   python tools/game_installer.py --install <game_number> [--upscaler xess]
   ```
   Or close the game, extract the package and run the installer with the folder of the game's `.exe`:
   - Windows: `install.cmd`
   - Linux and Steam Deck (Proton): `sh install.sh "<folder>"`, then set the game's launch options to the line it
     prints: `WINEDLLOVERRIDES="dxgi=n,b" %command%`, or `winmm=n,b` in Vulkan games
3. In the game, turn on frame generation (the NVIDIA option where the game offers several).

To uninstall, run `python tools/game_installer.py --uninstall <game_number>`, `uninstall.cmd` or `sh uninstall.sh` with the same folder.

## Supported GPUs

- NVIDIA GeForce RTX 20, 30, 40 and 50 series, and GTX 16 series
- AMD Radeon RX 5000, 6000, 7000 and 9000 series, and Steam Deck
- Intel Arc A and B series

On Windows 10 and 11, and on Linux and SteamOS with Proton.

## Results and problems

Please post them as [issues](../../issues/new/choose):
- **Performance results**: run the test kit from the release and attach its result file.
- **Problems**: the game, GPU and driver, operating system, settings and what you saw, with the newest `nr_fg-*.log`
  from under the game's `OptiScaler/custom/Apex Neural Rendering FG` folder.

OptiScaler is GPL-3.0; its source for each release is attached to the release.

## Record and compare frame generation

nr-record records the inputs a game gives its frame generation, losslessly. You can then replay a recording through any frame generation DLL you have (ANR FG, a game's DLSS-G `nvngx_dlssg.dll`) and compare the results as videos or images. nr-record includes no frame generation.

Requirements:
- a D3D12 or Vulkan game with DLSS frame generation, with the `anr-fg-full` package installed (it includes OptiScaler);
- Windows 10 or 11, or Linux with Proton;
- [ffmpeg](https://ffmpeg.org/download.html) and ffprobe on the `PATH`;
- for DLSS-G replays, an NVIDIA RTX 40 or 50 series GPU.

1. **Install.** Download `nr-record-1.2-windows.zip` or `nr-record-1.2-linux.tar.gz` from the [FG-V.B18 release](../../releases/tag/FG-V.B18) and extract it. Close the game and run the installer with the folder of the game's `.exe`:
   - Windows: `install.cmd "<folder>"`. No launch option is needed.
   - Linux and Steam Deck (Proton): `sh install.sh "<folder>"`. Set the game's Steam launch options to `WINEDLLOVERRIDES="dxgi=n,b" %command%` (the ANR FG installer prints the same line). Do not set this on Windows: the game may not start.

   The installer copies `nr-record` into `OptiScaler/custom/` and sets `FGNvngxReplacement=nr-record` in `OptiScaler.ini` (it keeps the original). When you are not recording, ANR FG generates the frames, or DLSS-G if ANR FG is not installed (`forward` in `nr-record/dlssg/nr_record.ini`). `uninstall.cmd` or `sh uninstall.sh` with the same folder removes nr-record and restores `OptiScaler.ini`. To install by hand: copy `capture/OptiScaler/custom/nr-record` into `OptiScaler/custom/`, set `FGNvngxReplacement=nr-record`, and set `forward` to `..\..\Apex Neural Rendering FG\dlssg\nvngx_dlssg.dll` or `nvidia`.
2. **Record.** Turn on DLSS frame generation in the game. **F6** starts and stops a recording; **F9** records the next 8 frames. Each start and stop beeps. While recording, the game shows only real frames. Recordings go to `%LOCALAPPDATA%\nr-record\` (Windows) or `~/.local/share/nr-record/` (Proton). A frame takes about 26 MB at 3840x2160 and 6 MB at 1806x972. `nr-record/dlssg/nr_record-<date>-<time>.log` lists what was recorded.

   To record the upscaler's inputs instead (super resolution, D3D12 games): open OptiScaler's menu (**Insert**), pick `nr-record` in the upscaler list, and press **F6** to start and stop. It upscales with the upscaler `OptiScaler.ini` names (DLSS on NVIDIA, else FSR, or XeSS) and records that output too. Pick your upscaler again afterwards. Replay these recordings with `--generator dlss`, `fsr` or `xess` ([replay](record/replay/README.md#sr-and-rr)).
3. **Replay.** On Windows, in the package folder (`REC` is a recording's folder):

   ```bat
   python tools\nr_compare.py --record REC --out out\cmp --generator provider --dll "<ANR FG folder>\nvngx_dlssg.dll" --label "ANR FG" --b-generator nvidia --b-dll "<game>\nvngx_dlssg.dll" --b-label DLSS-G --view
   ```

   Or run each step by hand:

   ```bat
   tools\nr-record.exe info REC
   tools\nr-replay.exe --record REC --out out\anr --generator provider --dll "<ANR FG folder>\nvngx_dlssg.dll" --label "ANR FG" --stream - | tools\nr-video.exe video - --out out\anr.mp4
   tools\nr-replay.exe --record REC --out out\dlssg --generator nvidia --dll "<game>\nvngx_dlssg.dll" --label DLSS-G --stream - | tools\nr-video.exe video - --out out\dlssg.mp4
   tools\nr-video.exe project out\anr.mp4 out\dlssg.mp4 --out out\cmp.compare.json --labels "ANR FG" DLSS-G
   ```

   On Linux, one command runs both replays under Proton's Wine and writes both videos, a side-by-side video and the compare project:

   ```bash
   python3 tools/nr_replay_wine.py --record REC --out cmp --video \
       --generator provider --dll "<ANR FG folder>/nvngx_dlssg.dll" --label "ANR FG" \
       --b-generator nvidia --b-dll "<game>/nvngx_dlssg.dll" --b-label DLSS-G
   ```

   For images, replay with `--raw` instead of `--stream` and run `nr-video png`.
4. **Compare.** `viewer/renderer --compare --project cmp/compare.json` (Windows: `viewer\renderer.exe --compare --project out\cmp.compare.json`) plays both videos in sync, with a divider, side by side view, pixel zoom and marks, and exports videos and images. From the command line: `--compare-export PROJECT --out FILE --very-high`. `viewer/renderer --captures` lists your recordings and regenerates their frames with each generator.

Docs: [recording](record/README.md), [format](record/FORMAT.md), [replay and videos](record/replay/README.md), [viewer](renderer/README.md).

Build with Bazel: `bazel build //record:nr-record //record/replay:nr-video //renderer`; Windows parts: `bazel build --config=windows_cross //record/capture:package //record/replay:nr-replay`.

Build core tools with CMake: `cmake -B build && cmake --build build --config Release`.

### Productivity Tools & Stability Features

- **ANR SR Native Super Resolution Engine**: Built-in temporal reconstruction engine (`record/anr_sr_upscaler.*`, `record/replay/anr_sr_generator.*`) with motion vector reprojection, sub-pixel jitter cancellation, and YCoCg variance clipping anti-ghosting.
- **ANR RR Native Ray Reconstruction Engine**: Built-in neural ray tracing denoiser (`record/anr_rr_denoiser.*`, `record/replay/anr_rr_generator.*`) with joint bilateral G-buffer guided filtering (normals, roughness, depth), virtual parallax reprojection for glossy specular reflections, and luminance demodulation/remodulation.
- **ANR Studio GUI (`tools/anr_studio.py` / `tools/anr_studio.ps1`)**: Native 1-click launcher and manager to scan installed games, pick Super Resolution & Frame Generation providers, configure Hardware Flip Metering & Reflex/Anti-Lag pacing, stabilize translucency, and launch games directly.
- **Hardware Flip Metering & Dynamic Pacing**: Ultra-low-latency display scanout synchronization and queue regulation for AMD RX 7000/9000 and NVIDIA RTX 4000/5000 GPUs.
- **Intel XeSS Frame Generation Replay Engine**: Complete XeSS-FG replay provider in `nr-replay` (`tools/xess_fg_generator.*`) enabling cross-vendor comparison between ANR FG, DLSS-G, FSR 3.1, and XeSS-FG.
- **Apple Silicon Native Metal Backend & MSL Compute**: Added `record/metal_ring.*` and MSL compute kernels (`record/record_pack.metal`) supporting zero-copy UMA capture on macOS M-series chips.
- **Universal Hardware Video Exporter (`tools/nr_export.py` / `tools/nr_export.ps1`)**: Hardware-accelerated 10-bit AV1/HEVC/H.264 exporter with automatic GPU vendor detection (Intel QuickSync, NVIDIA NVENC, AMD AMF, Apple VideoToolbox, and CPU fallback).
- **Mathematical Quality Evaluator (`tools/nr_metrics.py` / `tools/nr_metrics.ps1`)**: Computes exact PSNR, SSIM, and temporal stability metrics between reference and generated frames with NaN-safe vectorized pipelines.
- **Procedural 3D Scene Engine & Study Viewer**: Integrated real-time rasterization testbed and double-blind perceptual quality evaluation suite (`renderer/scene_missing.cpp`, `renderer/study_missing.cpp`).
- **1-Click Windows Comparison Tool (`tools/nr_compare.py` / `tools/nr_compare.ps1`)**: Automates replaying, video extraction, and side-by-side comparison.
- **Game Auto-Detector & Installer (`tools/game_installer.py` / `tools/game_installer.ps1`)**: Automatically scans Steam and Epic libraries and installs capture DLLs.
- **Comprehensive Compatibility Fixes**: Dynamic subrect scaling (*No Man's Sky*), Streamline memory safety (*MSFS 2020 & 2024*), non-AVX2 baseline support, dynamic frame delta tracking (*Crimson Desert* & *Control*), descriptor ring expansion (*Like a Dragon*), and translucency stabilization (*Wuthering Waves*).

## Contributors

- **k0u3h1k** ([@k0u3h1k](https://github.com/k0u3h1k)) — Performance optimizations, FSR 3 / FidelityFX FG replay engine, Reflex/Anti-Lag low-latency frame pacing, ANR Studio GUI, Universal Video Exporter, Mathematical Quality Evaluator, 1-Click Comparison Runner, Game Auto-Installer, comprehensive bug fixes, and CMake build system. See [CONTRIBUTORS.md](CONTRIBUTORS.md).

## Citation

```bibtex
@software{apex_neural_rendering,
  author = {{Apex Compute}},
  title  = {Apex Neural Rendering (ANR)},
  year   = {2026},
  url    = {https://github.com/apex-compute/ANR},
  note   = {https://apexcompute.com/neural-rendering}
}
```

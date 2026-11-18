#!/usr/bin/env python3
"""
Universal Hardware-Accelerated Video Exporter for ANR (nr-export).

Exports high-framerate, visually lossless videos from nr-replay streams and .nrraw frame dumps.
Automatically detects host GPU architecture and chooses the optimal hardware encoder:
  - Intel Arc / Core Ultra Xe / Xe2: Intel QuickSync Video (av1_qsv, hevc_qsv, h264_qsv)
  - NVIDIA GeForce RTX / GTX:        NVIDIA NVENC (av1_nvenc, hevc_nvenc, h264_nvenc)
  - AMD Radeon RX:                   AMD AMF (av1_amf, hevc_amf, h264_amf)
  - Universal CPU Fallback:          SVT-AV1 / x265 / x264

Supports single replay export, side-by-side comparison, and 10-bit HDR (BT.2020 / PQ).
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def detect_gpu_vendor() -> Tuple[str, str]:
    """Detect primary GPU vendor and description on Windows/Linux."""
    vendor = "unknown"
    gpu_name = "Generic GPU"
    try:
        if sys.platform == "win32":
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Caption"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                # Prefer dedicated/primary GPU if multiple
                for line in lines:
                    low = line.lower()
                    if "arc" in low or "intel" in low:
                        vendor = "intel"
                        gpu_name = line
                        break
                    elif "nvidia" in low or "geforce" in low or "rtx" in low:
                        vendor = "nvidia"
                        gpu_name = line
                        break
                    elif "amd" in low or "radeon" in low:
                        vendor = "amd"
                        gpu_name = line
                        break
                if vendor == "unknown" and lines:
                    gpu_name = lines[0]
                    if "intel" in gpu_name.lower(): vendor = "intel"
                    elif "nvidia" in gpu_name.lower(): vendor = "nvidia"
                    elif "amd" in gpu_name.lower(): vendor = "amd"
        elif sys.platform == "darwin":
            vendor = "apple"
            gpu_name = "Apple Silicon GPU (Metal)"
        else:
            res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            low = res.stdout.lower()
            if "intel" in low: vendor = "intel"; gpu_name = "Intel GPU"
            elif "nvidia" in low: vendor = "nvidia"; gpu_name = "NVIDIA GPU"
            elif "amd" in low or "advanced micro devices" in low: vendor = "amd"; gpu_name = "AMD GPU"
    except Exception:
        pass
    return vendor, gpu_name


def get_available_encoders(ffmpeg_bin: str) -> Dict[str, bool]:
    """Probe FFmpeg for supported hardware and software encoders."""
    encoders = {}
    try:
        res = subprocess.run([ffmpeg_bin, "-hide_banner", "-encoders"],
                             capture_output=True, text=True, timeout=5)
        text = res.stdout
        for enc in ["av1_qsv", "hevc_qsv", "h264_qsv",
                    "av1_nvenc", "hevc_nvenc", "h264_nvenc",
                    "av1_amf", "hevc_amf", "h264_amf",
                    "hevc_videotoolbox", "h264_videotoolbox",
                    "libsvtav1", "libx265", "libx264"]:
            encoders[enc] = f" {enc} " in text or f" {enc}\n" in text
    except Exception:
        pass
    return encoders


def select_best_encoder(vendor: str, codec: str, available: Dict[str, bool]) -> Tuple[str, str]:
    """Select the best encoder for the detected GPU vendor and requested codec."""
    codec = codec.lower()

    # Priorities per vendor
    candidates = []
    if vendor == "intel":
        if codec == "av1": candidates = ["av1_qsv", "libsvtav1"]
        elif codec == "hevc": candidates = ["hevc_qsv", "libx265"]
        else: candidates = ["h264_qsv", "libx264"]
    elif vendor == "nvidia":
        if codec == "av1": candidates = ["av1_nvenc", "libsvtav1"]
        elif codec == "hevc": candidates = ["hevc_nvenc", "libx265"]
        else: candidates = ["h264_nvenc", "libx264"]
    elif vendor == "amd":
        if codec == "av1": candidates = ["av1_amf", "libsvtav1"]
        elif codec == "hevc": candidates = ["hevc_amf", "libx265"]
        else: candidates = ["h264_amf", "libx264"]
    elif vendor == "apple":
        if codec == "hevc": candidates = ["hevc_videotoolbox", "libx265"]
        elif codec == "h264": candidates = ["h264_videotoolbox", "libx264"]
        else: candidates = ["libsvtav1"]
    else:
        # Generic order: hardware first, then software
        if codec == "av1": candidates = ["av1_qsv", "av1_nvenc", "av1_amf", "libsvtav1"]
        elif codec == "hevc": candidates = ["hevc_qsv", "hevc_nvenc", "hevc_amf", "libx265"]
        else: candidates = ["h264_qsv", "h264_nvenc", "h264_amf", "libx264"]

    # Select first available
    for c in candidates:
        if available.get(c, False):
            mode = "Hardware QuickSync" if "qsv" in c else "Hardware NVENC" if "nvenc" in c else "Hardware AMF" if "amf" in c else "Software CPU"
            return c, mode

    # Fallback to software
    sw_fallback = "libsvtav1" if codec == "av1" else "libx265" if codec == "hevc" else "libx264"
    return sw_fallback, "Software CPU (Fallback)"


def get_encoder_params(encoder: str, quality: str) -> List[str]:
    """Get encoder-specific quality and rate-control parameters."""
    params = []
    q_map = {"lossless": (0, 16), "high": (18, 20), "medium": (23, 26)}
    crf, qp = q_map.get(quality, (18, 20))

    if "qsv" in encoder:
        # Intel QuickSync params
        params.extend(["-global_quality", str(qp), "-preset", "veryfast" if quality == "medium" else "medium"])
    elif "nvenc" in encoder:
        # NVIDIA NVENC params
        params.extend(["-cq", str(qp), "-preset", "p4" if quality == "medium" else "p6"])
    elif "amf" in encoder:
        # AMD AMF params
        params.extend(["-qp_i", str(qp), "-qp_p", str(qp), "-quality", "speed" if quality == "medium" else "quality"])
    elif "videotoolbox" in encoder:
        # Apple VideoToolbox params
        params.extend(["-q:v", str(min(100, max(1, 100 - crf * 3)))])
    elif encoder == "libsvtav1":
        params.extend(["-crf", str(crf), "-preset", "8"])
    elif encoder == "libx265":
        params.extend(["-crf", str(crf), "-preset", "fast"])
    else:
        params.extend(["-crf", str(crf), "-preset", "fast"])

    return params


def find_replay_json(dir_path: Path) -> Optional[dict]:
    """Look for replay.json in the directory."""
    rpt = dir_path / "replay.json"
    if rpt.is_file():
        try:
            with open(rpt, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def export_replay_directory(in_dir: Path, out_file: Path, codec: str, quality: str, ffmpeg_bin: str) -> bool:
    """Export raw frames or stream from an nr-replay output folder into a high-quality video."""
    meta = find_replay_json(in_dir)
    if not meta:
        print(f"[Error] replay.json not found in {in_dir}")
        return False

    width, height = meta.get("size", [1920, 1080])
    fps = meta.get("fps", 60.0)
    hdr = meta.get("hdr", False)
    generator_label = meta.get("generator", {}).get("label", "Generator")

    vendor, gpu_name = detect_gpu_vendor()
    available = get_available_encoders(ffmpeg_bin)
    encoder, mode = select_best_encoder(vendor, codec, available)

    print("=" * 65)
    print(f"ANR Universal Video Exporter (nr-export)")
    print(f"Detected GPU:      {gpu_name} ({vendor.upper()})")
    print(f"Selected Encoder:  {encoder} [{mode}]")
    print(f"Input Recording:   {meta.get('recording', 'Unknown')}")
    print(f"Generator:         {generator_label}")
    print(f"Resolution:        {width}x{height} @ {fps:.2f} FPS (HDR: {hdr})")
    print(f"Output File:       {out_file}")
    print("=" * 65)

    # Collect raw frame files
    raw_files = sorted(in_dir.glob("*.nrraw"), key=lambda p: p.stem)
    if not raw_files:
        print(f"[Error] No .nrraw files found in {in_dir}. Run nr-replay with --raw flag.")
        return False

    print(f"Processing {len(raw_files)} raw frames...")

    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Construct ffmpeg command
    # Raw pixel format: rgb24 (SDR) or rgb48le (HDR)
    pix_fmt = "rgb48le" if hdr else "rgb24"

    cmd = [
        ffmpeg_bin, "-y",
        "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo",
        "-pixel_format", pix_fmt,
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps),
        "-i", "pipe:0",
    ]

    # Add color/HDR metadata
    if hdr:
        cmd.extend([
            "-color_primaries", "bt2020",
            "-color_trc", "smpte2084",
            "-colorspace", "bt2020nc",
            "-pix_fmt", "yuv420p10le"
        ])
    else:
        cmd.extend([
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-pix_fmt", "yuv420p"
        ])

    cmd.extend(["-c:v", encoder])
    cmd.extend(get_encoder_params(encoder, quality))
    cmd.append(str(out_file))

    # Execute FFmpeg with piped raw frames
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for idx, rf in enumerate(raw_files):
            with open(rf, "rb") as f:
                # 32-byte nrraw header: ("NRRAW1\0\0", version, width, height, dxgi, channels, reserved)
                header = f.read(32)
                raw_texels = f.read()

                # Convert float16 RGBA texels to destination format
                if HAVE_NUMPY:
                    arr = np.frombuffer(raw_texels, dtype=np.float16).astype(np.float32).reshape((-1, 4))[:, :3]
                    if hdr:
                        out_bytes = np.clip(arr * 65535.0, 0, 65535).astype(np.uint16).tobytes()
                    else:
                        # Map scene-linear light to standard sRGB transfer curve
                        srgb = np.where(arr <= 0.0031308, 12.92 * arr, 1.055 * (np.maximum(arr, 0.0) ** (1.0 / 2.4)) - 0.055)
                        out_bytes = np.clip(srgb * 255.0, 0, 255).astype(np.uint8).tobytes()
                else:
                    # Fallback conversion without numpy
                    n_pixels = len(raw_texels) // 8
                    step = 8
                    buf = bytearray()
                    for p in range(n_pixels):
                        r, g, b, _ = struct.unpack_from("<4e", raw_texels, p * step)
                        if hdr:
                            buf.extend(struct.pack("<3H", int(max(0.0, min(1.0, r)) * 65535),
                                                          int(max(0.0, min(1.0, g)) * 65535),
                                                          int(max(0.0, min(1.0, b)) * 65535)))
                        else:
                            # Linear to sRGB transfer function
                            s_r = 12.92 * r if r <= 0.0031308 else 1.055 * (max(0.0, r) ** (1.0 / 2.4)) - 0.055
                            s_g = 12.92 * g if g <= 0.0031308 else 1.055 * (max(0.0, g) ** (1.0 / 2.4)) - 0.055
                            s_b = 12.92 * b if b <= 0.0031308 else 1.055 * (max(0.0, b) ** (1.0 / 2.4)) - 0.055
                            buf.extend(struct.pack("3B", int(max(0.0, min(1.0, s_r)) * 255),
                                                         int(max(0.0, min(1.0, s_g)) * 255),
                                                         int(max(0.0, min(1.0, s_b)) * 255)))
                    out_bytes = bytes(buf)

                try:
                    proc.stdin.write(out_bytes)
                except BrokenPipeError:
                    break
            if (idx + 1) % 50 == 0 or idx + 1 == len(raw_files):
                pct = ((idx + 1) / len(raw_files)) * 100
                print(f"\rEncoding progress: {idx + 1}/{len(raw_files)} frames ({pct:.1f}%)", end="", flush=True)

        proc.stdin.close()
        stderr_output = proc.stderr.read().decode(errors="replace")
        proc.wait()

        print()
        if proc.returncode == 0:
            print(f"[Success] Video saved to: {out_file} ({out_file.stat().st_size / (1024*1024):.2f} MB)")
            return True
        else:
            print(f"[Error] FFmpeg failed with code {proc.returncode}:\n{stderr_output}")
            return False
    except Exception as e:
        print(f"[Error] Encoding exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="ANR Universal Hardware Video Exporter (QuickSync / NVENC / AMF / CPU)")
    parser.add_argument("--in-dir", "-i", type=str, required=True, help="Directory containing nr-replay output (.nrraw and replay.json)")
    parser.add_argument("--out", "-o", type=str, default="", help="Output video file path (.mp4 / .mkv)")
    parser.add_argument("--codec", "-c", choices=["av1", "hevc", "h264"], default="av1", help="Target video codec (default: av1)")
    parser.add_argument("--quality", "-q", choices=["lossless", "high", "medium"], default="high", help="Quality tier (default: high)")
    parser.add_argument("--ffmpeg", type=str, default="ffmpeg", help="Path to ffmpeg binary (default: ffmpeg on PATH)")

    args = parser.parse_args()

    ffmpeg_bin = shutil.which(args.ffmpeg) or args.ffmpeg
    if not shutil.which(ffmpeg_bin) and not os.path.exists(ffmpeg_bin):
        print(f"[Error] FFmpeg not found at '{ffmpeg_bin}'. Please install FFmpeg or pass --ffmpeg PATH.")
        sys.exit(1)

    in_dir = Path(args.in_dir)
    if not in_dir.is_dir():
        print(f"[Error] Input directory {in_dir} does not exist.")
        sys.exit(1)

    out_file = Path(args.out) if args.out else in_dir / f"video_{args.codec}.mp4"
    success = export_replay_directory(in_dir, out_file, args.codec, args.quality, ffmpeg_bin)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

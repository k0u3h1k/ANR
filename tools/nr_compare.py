#!/usr/bin/env python3
"""Automated frame generation and upscaling comparison runner for Windows and Linux.

Runs two implementations on an nr-record capture, streams them through nr-video to
encode MP4s, generates a lockstep compare project (.compare.json), and optionally
opens the interactive renderer comparison GUI.

Example:
    python tools/nr_compare.py --record %LOCALAPPDATA%\\nr-record\\20261111-game --out out\\cmp \\
        --generator provider --dll "C:\\path\\to\\nvngx_dlssg.dll" --label "ANR FG" \\
        --b-generator nvidia --b-dll "C:\\game\\nvngx_dlssg.dll" --b-label "DLSS-G" \\
        --view
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def find_binary(name, custom_path=None):
    if custom_path and Path(custom_path).is_file():
        return Path(custom_path).resolve()

    candidates = [
        HERE / name,
        HERE / f"{name}.exe",
        REPO_ROOT / "tools" / name,
        REPO_ROOT / "tools" / f"{name}.exe",
        REPO_ROOT / "bazel-bin" / "record" / "replay" / name,
        REPO_ROOT / "bazel-bin" / "record" / "replay" / f"{name}.exe",
        REPO_ROOT / "bazel-bin" / "renderer" / name,
        REPO_ROOT / "bazel-bin" / "renderer" / f"{name}.exe",
        REPO_ROOT / "build" / "bin" / name,
        REPO_ROOT / "build" / "bin" / f"{name}.exe",
        REPO_ROOT / "build" / "Release" / f"{name}.exe",
    ]

    for c in candidates:
        if c.is_file():
            return c.resolve()

    on_path = shutil.which(name)
    if on_path:
        return Path(on_path).resolve()

    return None


def run_pipeline(replay_bin, video_bin, record_dir, out_dir, generator, dll, label,
                 video_out, frames=None, multiplier=None, mode=None, preset=None):
    cmd_replay = [
        str(replay_bin),
        "--record", str(record_dir),
        "--out", str(out_dir),
        "--generator", generator,
        "--stream", "-"
    ]
    if dll:
        cmd_replay += ["--dll", str(dll)]
    if label:
        cmd_replay += ["--label", label]
    if frames:
        cmd_replay += ["--frames", frames]
    if multiplier:
        cmd_replay += ["--multiplier", str(multiplier)]
    if mode:
        cmd_replay += ["--mode", mode]
    if preset:
        cmd_replay += ["--preset", preset]

    cmd_video = [
        str(video_bin),
        "video", "-",
        "--out", str(video_out)
    ]

    print(f"[*] Replaying '{label or generator}' -> {video_out.name}...")
    start_t = time.time()

    p_replay = subprocess.Popen(cmd_replay, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p_video = subprocess.Popen(cmd_video, stdin=p_replay.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p_replay.stdout.close()

    v_out, v_err = p_video.communicate()
    r_out, r_err = p_replay.communicate()

    if p_replay.returncode != 0:
        print(f"[!] nr-replay error ({p_replay.returncode}):\n{r_err.decode(errors='replace')}", file=sys.stderr)
        return False
    if p_video.returncode != 0:
        print(f"[!] nr-video error ({p_video.returncode}):\n{v_err.decode(errors='replace')}", file=sys.stderr)
        return False

    elapsed = time.time() - start_t
    print(f"[+] Finished '{label or generator}' in {elapsed:.2f}s")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", "-r", type=Path, required=True, help="Path to nr-record capture folder")
    parser.add_argument("--out", "-o", type=Path, default=Path("out/cmp"), help="Output directory")

    parser.add_argument("--generator", "-g", required=True,
                        choices=("provider", "nvidia", "dlss", "dlssd", "ngx", "fsr", "ffx", "xess", "anr", "anr-sr", "anr-rr", "recorded"),
                        help="First generator")
    parser.add_argument("--dll", type=Path, help="DLL path for first generator")
    parser.add_argument("--label", "-l", default="A", help="Label for first generator (e.g. 'ANR FG')")

    parser.add_argument("--b-generator", "-bg",
                        choices=("provider", "nvidia", "dlss", "dlssd", "ngx", "fsr", "ffx", "xess", "anr", "anr-sr", "anr-rr", "recorded"),
                        help="Second generator for comparison")
    parser.add_argument("--b-dll", type=Path, help="DLL path for second generator")
    parser.add_argument("--b-label", "-bl", default="B", help="Label for second generator (e.g. 'DLSS-G')")

    parser.add_argument("--frames", help="Frame range (e.g. 0:60)")
    parser.add_argument("--multiplier", type=int, help="Multiplier (e.g. 2)")
    parser.add_argument("--mode", choices=("interleaved", "generated"), help="Display mode")
    parser.add_argument("--preset", help="DLSS render preset")

    parser.add_argument("--view", action="store_true", help="Launch interactive renderer GUI when done")
    parser.add_argument("--replay-bin", type=Path, help="Custom path to nr-replay binary")
    parser.add_argument("--video-bin", type=Path, help="Custom path to nr-video binary")
    parser.add_argument("--renderer-bin", type=Path, help="Custom path to renderer binary")

    args = parser.parse_args()

    record_path = args.record.resolve()
    if not (record_path / "record.json").exists():
        sys.exit(f"Error: {record_path} is not a valid nr-record directory (missing record.json).")

    replay_exe = find_binary("nr-replay", args.replay_bin)
    video_exe = find_binary("nr-video", args.video_bin)
    renderer_exe = find_binary("renderer", args.renderer_bin)

    if not replay_exe:
        sys.exit("Error: Could not locate 'nr-replay'. Specify --replay-bin or build with Bazel/CMake.")
    if not video_exe:
        sys.exit("Error: Could not locate 'nr-video'. Specify --video-bin or build with Bazel/CMake.")

    args.out.mkdir(parents=True, exist_ok=True)

    out_a = args.out / "a"
    out_a.mkdir(parents=True, exist_ok=True)
    video_a = args.out / "video_a.mp4"

    ok = run_pipeline(replay_exe, video_exe, record_path, out_a, args.generator, args.dll, args.label,
                      video_a, args.frames, args.multiplier, args.mode, args.preset)
    if not ok:
        sys.exit(1)

    project_file = None
    if args.b_generator:
        out_b = args.out / "b"
        out_b.mkdir(parents=True, exist_ok=True)
        video_b = args.out / "video_b.mp4"

        ok = run_pipeline(replay_exe, video_exe, record_path, out_b, args.b_generator, args.b_dll, args.b_label,
                          video_b, args.frames, args.multiplier, args.mode, args.preset)
        if not ok:
            sys.exit(1)

        project_file = args.out / "compare.compare.json"
        cmd_proj = [
            str(video_exe),
            "project", str(video_a), str(video_b),
            "--out", str(project_file),
            "--labels", args.label, args.b_label
        ]
        print(f"[*] Creating comparison project -> {project_file}...")
        subprocess.run(cmd_proj, check=True)
        print(f"[+] Compare project saved: {project_file}")

    print("\n[✓] Comparison pipeline completed successfully!")
    print(f"    Video A: {video_a}")
    if args.b_generator:
        print(f"    Video B: {args.out / 'video_b.mp4'}")
        print(f"    Project: {project_file}")

    if args.view:
        if not renderer_exe:
            print("[!] Cannot launch viewer: 'renderer' binary not found. Build //renderer to use GUI.", file=sys.stderr)
            return

        cmd_view = [str(renderer_exe), "--compare"]
        if project_file:
            cmd_view += ["--project", str(project_file)]
        print(f"[*] Launching renderer GUI: {' '.join(cmd_view)}")
        subprocess.Popen(cmd_view)


if __name__ == "__main__":
    main()

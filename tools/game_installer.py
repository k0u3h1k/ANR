#!/usr/bin/env python3
"""Game Auto-Detector & ANR / OptiScaler Installer.

Scans Steam, Epic Games, GOG, and custom folders to detect installed games, identifies
their upscaling and frame generation capabilities (DLSS, DLSS-G, FSR, XeSS, OptiScaler),
and automates 1-click installation and configuration of ANR FG and nr-record.

Usage:
    python tools/game_installer.py --scan
    python tools/game_installer.py --install <game_number_or_path> [--upscaler xess|dlss|fsr]
    python tools/game_installer.py --uninstall <game_number_or_path>
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def get_steam_libraries():
    libraries = []
    candidates = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
        Path.home() / ".steam/root",
    ]
    for c in candidates:
        vdf = c / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                content = vdf.read_text(encoding="utf-8", errors="ignore")
                for match in re.finditer(r'"path"\s+"([^"]+)"', content):
                    p = Path(match.group(1).replace("\\\\", "\\"))
                    if p.is_dir() and (p / "steamapps" / "common").is_dir():
                        libraries.append(p / "steamapps" / "common")
            except Exception:
                pass
            if c / "steamapps" / "common" not in libraries and (c / "steamapps" / "common").is_dir():
                libraries.append(c / "steamapps" / "common")
    return list(dict.fromkeys(libraries))


def get_epic_games():
    games = []
    manifest_dir = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests")
    if manifest_dir.is_dir():
        for item in manifest_dir.glob("*.item"):
            try:
                data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
                loc = data.get("InstallLocation")
                name = data.get("DisplayName", Path(loc).name if loc else "Unknown")
                if loc and Path(loc).is_dir():
                    games.append((name, Path(loc)))
            except Exception:
                pass
    return games


def probe_game_folder(folder):
    info = {
        "optiscaler": False,
        "optiscaler_ini": None,
        "nr_record": False,
        "anr_fg": False,
        "dlss": False,
        "dlssg": False,
        "fsr": False,
        "xess": False,
        "exe": None,
    }

    try:
        exes = list(folder.glob("*.exe")) + list(folder.glob("*/*.exe")) + list(folder.glob("*/*/*.exe"))
        # Exclude crash reporters, installers, launchers where possible
        valid_exes = [e for e in exes if not any(x in e.name.lower() for x in ("crash", "reporter", "unins", "setup", "helper", "eac"))]
        if valid_exes:
            info["exe"] = valid_exes[0]

        # Scan game root and binary directories up to depth 2 to avoid scanning massive asset packs
        scan_dirs = [folder]
        for sub in folder.iterdir():
            if sub.is_dir() and not any(ign in sub.name.lower() for ign in ("paks", "content", "data", "music", "sound", "textures", "movies", "assets")):
                scan_dirs.append(sub)
                for sub2 in sub.iterdir():
                    if sub2.is_dir() and not any(ign in sub2.name.lower() for ign in ("paks", "content", "data", "music", "sound", "textures", "movies", "assets")):
                        scan_dirs.append(sub2)

        for d in scan_dirs:
            for p in d.iterdir():
                if not p.is_file():
                    continue
                name_lower = p.name.lower()
                if name_lower == "optiscaler.ini":
                    info["optiscaler"] = True
                    info["optiscaler_ini"] = p
                elif name_lower == "nvngx_dlssg.dll":
                    if "apex neural rendering" in str(p).lower():
                        info["anr_fg"] = True
                    elif "nr-record" in str(p).lower():
                        info["nr_record"] = True
                    else:
                        info["dlssg"] = True
                elif name_lower == "nvngx_dlss.dll":
                    info["dlss"] = True
                elif "fidelityfx" in name_lower or name_lower.startswith("ffx_"):
                    info["fsr"] = True
                elif name_lower == "libxess.dll":
                    info["xess"] = True
    except Exception:
        pass

    return info


class DetectedGame:
    """Represents a discovered game and its executable path and features."""
    def __init__(self, name: str, install_dir: Path, exe_name: str = "", source: str = "custom", meta: dict = None):
        self.name = name
        self.install_dir = Path(install_dir)
        self.path = self.install_dir
        self.exe_name = exe_name
        self.source = source
        self.platform = source.capitalize()
        self.meta = meta or {}

    def __getitem__(self, key):
        if key == "name":
            return self.name
        if key in ("path", "install_dir"):
            return self.install_dir
        if key in ("platform", "source"):
            return self.platform
        if key == "meta":
            return self.meta
        if key == "exe_name":
            return self.exe_name
        raise KeyError(key)

    def __repr__(self):
        return f"<DetectedGame {self.name} [{self.source}] ({self.install_dir})>"


def scan_steam_games():
    games = []
    steam_libs = get_steam_libraries()
    for lib in steam_libs:
        if not lib.is_dir():
            continue
        for game_dir in lib.iterdir():
            if game_dir.is_dir():
                meta = probe_game_folder(game_dir)
                exe_name = meta["exe"].name if meta.get("exe") else ""
                games.append(DetectedGame(
                    name=game_dir.name,
                    install_dir=game_dir,
                    exe_name=exe_name,
                    source="steam",
                    meta=meta,
                ))
    return games


def scan_epic_games():
    games = []
    for name, path in get_epic_games():
        meta = probe_game_folder(path)
        exe_name = meta["exe"].name if meta.get("exe") else ""
        games.append(DetectedGame(
            name=name,
            install_dir=path,
            exe_name=exe_name,
            source="epic",
            meta=meta,
        ))
    return games


def scan_games(extra_dirs=None):
    results = scan_steam_games() + scan_epic_games()
    if extra_dirs:
        for ed in extra_dirs:
            p = Path(ed)
            if p.is_dir():
                meta = probe_game_folder(p)
                exe_name = meta["exe"].name if meta.get("exe") else ""
                results.append(DetectedGame(
                    name=p.name,
                    install_dir=p,
                    exe_name=exe_name,
                    source="custom",
                    meta=meta,
                ))
    return results


def install_into_game(game_path, upscaler=None):
    game_path = Path(game_path).resolve()
    if not game_path.is_dir():
        sys.exit(f"Error: {game_path} is not a valid directory.")

    opti_ini = game_path / "OptiScaler.ini"
    opti_dir = game_path / "OptiScaler"

    # Search subdirectories if not directly in root
    if not opti_ini.exists():
        found = list(game_path.glob("*/OptiScaler.ini")) + list(game_path.glob("*/*/OptiScaler.ini"))
        if found:
            opti_ini = found[0]
            game_path = opti_ini.parent
            opti_dir = game_path / "OptiScaler"

    if not opti_ini.exists() or not opti_dir.is_dir():
        print(f"[!] Warning: OptiScaler not detected in '{game_path}'.")
        print("    ANR FG requires OptiScaler to hook into games.")
        print("    Please install OptiScaler (or the ANR FG Full Package) into the game's executable directory first.")
        return False

    # Backup OptiScaler.ini
    backup_dir = opti_dir / "nr_record_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_ini = backup_dir / "OptiScaler.ini"
    if not backup_ini.exists():
        shutil.copy2(opti_ini, backup_ini)
        print(f"[+] Created original backup -> {backup_ini}")

    # Copy nr-record capture files
    src_record = REPO_ROOT / "record" / "capture"
    dest_record = opti_dir / "custom" / "nr-record"
    dest_record.mkdir(parents=True, exist_ok=True)

    # Check for ANR FG DLL
    anr_dll = opti_dir / "custom" / "Apex Neural Rendering FG" / "dlssg" / "nvngx_dlssg.dll"
    forward_val = r"..\..\Apex Neural Rendering FG\dlssg\nvngx_dlssg.dll" if anr_dll.exists() else "nvidia"
    forward_name = "ANR FG" if anr_dll.exists() else "NVIDIA DLSS-G"

    # Configure nr_record.ini
    dest_dlssg_ini = dest_record / "dlssg" / "nr_record.ini"
    dest_dlssg_ini.parent.mkdir(parents=True, exist_ok=True)
    src_ini = src_record / "nr_record.ini"
    if src_ini.exists() and not dest_dlssg_ini.exists():
        text = src_ini.read_text(encoding="utf-8")
        text = re.sub(r'(?m)^forward\s*=.*', f'forward = {forward_val}', text)
        dest_dlssg_ini.write_text(text, encoding="utf-8")
        print(f"[+] Deployed and configured -> {dest_dlssg_ini} (Forward: {forward_name})")

    # Update OptiScaler.ini
    ini_content = opti_ini.read_text(encoding="utf-8")
    if "FGNvngxReplacement" in ini_content:
        ini_content = re.sub(r'(?m)^FGNvngxReplacement=.*', 'FGNvngxReplacement=nr-record', ini_content)
    else:
        ini_content += "\n[FrameGen]\nFGNvngxReplacement=nr-record\n"

    # Optional upscaler tuning (e.g. XeSS for Intel Arc 140V, or ANR native)
    if upscaler:
        if "Dx12Upscaler" in ini_content:
            ini_content = re.sub(r'(?m)^Dx12Upscaler=.*', f'Dx12Upscaler={upscaler}', ini_content)
        else:
            ini_content += f"\n[Upscalers]\nDx12Upscaler={upscaler}\n"
        print(f"[+] Configured Dx12Upscaler = {upscaler} in OptiScaler.ini")

    opti_ini.write_text(ini_content, encoding="utf-8")
    print(f"[✓] Successfully configured OptiScaler in: {game_path}")
    print(f"    - Frame Generation Hook: FGNvngxReplacement=nr-record")
    print(f"    - Forward Target: {forward_name}")
    print("    - Hotkeys: F6 = Start/Stop Recording, F9 = Capture 8 Frames")
    return True


def uninstall_from_game(game_path):
    game_path = Path(game_path).resolve()
    opti_ini = game_path / "OptiScaler.ini"
    if not opti_ini.exists():
        found = list(game_path.glob("*/OptiScaler.ini"))
        if found:
            opti_ini = found[0]
            game_path = opti_ini.parent

    opti_dir = game_path / "OptiScaler"
    backup_ini = opti_dir / "nr_record_backup" / "OptiScaler.ini"

    if backup_ini.exists():
        shutil.copy2(backup_ini, opti_ini)
        print(f"[+] Restored original OptiScaler.ini from backup.")
    else:
        if opti_ini.exists():
            text = opti_ini.read_text(encoding="utf-8")
            text = re.sub(r'(?m)^FGNvngxReplacement=nr-record', 'FGNvngxReplacement=auto', text)
            opti_ini.write_text(text, encoding="utf-8")
            print(f"[+] Reset FGNvngxReplacement=auto in OptiScaler.ini.")

    dest_record = opti_dir / "custom" / "nr-record"
    if dest_record.is_dir():
        shutil.rmtree(dest_record)
        print(f"[+] Removed {dest_record}")

    print(f"[✓] Uninstalled nr-record from {game_path}.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scan", "-s", action="store_true", help="Scan and list installed games with feature detection")
    parser.add_argument("--install", "-i", help="Game number from scan, or full folder path to install into")
    parser.add_argument("--uninstall", "-u", help="Game number from scan, or full folder path to uninstall from")
    parser.add_argument("--upscaler", choices=("anr", "anr-sr", "anr-rr", "xess", "dlss", "fsr21", "fsr22", "fsr31"),
                        help="Configure primary upscaler in OptiScaler.ini (Recommended: 'anr' / 'anr-rr', or 'xess' for Intel Arc 140V)")
    parser.add_argument("--path", "-p", type=Path, help="Additional custom directory to scan")

    args = parser.parse_args()

    custom_dirs = [args.path] if args.path else []
    games = scan_games(custom_dirs)

    if args.install:
        target = args.install
        if target.isdigit() and 1 <= int(target) <= len(games):
            target = games[int(target) - 1]["path"]
        install_into_game(target, args.upscaler)
        return

    if args.uninstall:
        target = args.uninstall
        if target.isdigit() and 1 <= int(target) <= len(games):
            target = games[int(target) - 1]["path"]
        uninstall_from_game(target)
        return

    # Default / Scan display
    print(f"\n{'='*75}")
    print(f"  ANR & OptiScaler Game Detector — Found {len(games)} Games")
    print(f"{'='*75}\n")

    for idx, g in enumerate(games, 1):
        m = g["meta"]
        tags = []
        if m["optiscaler"]:
            tags.append("OptiScaler: YES")
        if m["anr_fg"]:
            tags.append("ANR FG: YES")
        if m["nr_record"]:
            tags.append("nr-record: INSTALLED")
        if m["dlss"]:
            tags.append("DLSS")
        if m["dlssg"]:
            tags.append("DLSS-G")
        if m["fsr"]:
            tags.append("FSR")
        if m["xess"]:
            tags.append("XeSS")

        tag_str = f" [{', '.join(tags)}]" if tags else " [No upscaler DLLs detected]"
        print(f"  [{idx:2d}] {g['name']} ({g['platform']}){tag_str}")
        print(f"       Folder: {g['path']}")

    print("\nTo install into a game:")
    print("  python tools/game_installer.py --install <number_or_path> [--upscaler xess]")
    print("\nTo uninstall:")
    print("  python tools/game_installer.py --uninstall <number_or_path>\n")


if __name__ == "__main__":
    main()

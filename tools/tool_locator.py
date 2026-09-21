#!/usr/bin/env python3
"""Locate workflow executables across PATH and common Windows installations."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator


SUPPORTED = ("xelatex", "typst", "drawio", "pdftoppm")
ENVIRONMENT_OVERRIDES = {
    "xelatex": "XELATEX_BIN",
    "typst": "TYPST_BIN",
    "drawio": "DRAWIO_BIN",
    "pdftoppm": "PDFTOPPM_BIN",
}
EXECUTABLE_NAMES = {
    "xelatex": ("xelatex", "xelatex.exe"),
    "typst": ("typst", "typst.exe"),
    "drawio": ("drawio", "draw.io", "drawio.exe", "draw.io.exe"),
    "pdftoppm": ("pdftoppm", "pdftoppm.exe"),
}


def _normalise_name(name: str) -> str:
    value = name.strip().lower()
    aliases = {"draw.io": "drawio", "draw.io.exe": "drawio", "drawio.exe": "drawio"}
    value = aliases.get(value, value.removesuffix(".exe"))
    if value not in SUPPORTED:
        raise ValueError(f"unsupported tool: {name}; choose from {', '.join(SUPPORTED)}")
    return value


def _usable(path: Path) -> bool:
    try:
        return path.expanduser().is_file()
    except OSError:
        return False


def _resolved(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _candidate(path: str | Path | None, source: str) -> Iterator[dict[str, str]]:
    if not path:
        return
    raw = os.path.expandvars(str(path).strip().strip('"'))
    if not raw:
        return
    value = Path(raw)
    if _usable(value):
        yield {"path": _resolved(value), "source": source}


def _logical_drives() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import ctypes

        mask = int(ctypes.windll.kernel32.GetLogicalDrives())
        return [Path(f"{chr(65 + index)}:/") for index in range(26) if mask & (1 << index)]
    except Exception:  # noqa: BLE001
        return [Path("C:/")]


def _display_icon_path(raw: str) -> str:
    value = os.path.expandvars(raw.strip())
    if value.startswith('"'):
        end = value.find('"', 1)
        if end > 1:
            return value[1:end]
    value = re.sub(r",\s*-?\d+\s*$", "", value)
    return value.strip().strip('"')


def _registry_candidates(tool: str) -> Iterator[dict[str, str]]:
    if os.name != "nt":
        return
    try:
        import winreg
    except ImportError:
        return

    match_terms = {
        "drawio": ("draw.io", "diagrams.net"),
        "xelatex": ("miktex", "tex live", "texlive"),
        "typst": ("typst",),
        "pdftoppm": ("poppler",),
    }[tool]
    uninstall_keys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    views = (0, getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0))
    seen_keys: set[tuple[int, str, int]] = set()
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key_name in uninstall_keys:
            for view in views:
                marker = (int(hive), key_name, view)
                if marker in seen_keys:
                    continue
                seen_keys.add(marker)
                try:
                    root = winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view)
                except OSError:
                    continue
                with root:
                    index = 0
                    while True:
                        try:
                            child_name = winreg.EnumKey(root, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            child = winreg.OpenKey(root, child_name)
                        except OSError:
                            continue
                        with child:
                            values: dict[str, str] = {}
                            for field in ("DisplayName", "DisplayIcon", "InstallLocation"):
                                try:
                                    values[field] = str(winreg.QueryValueEx(child, field)[0])
                                except OSError:
                                    values[field] = ""
                        display_name = values["DisplayName"].lower()
                        if not any(term in display_name for term in match_terms):
                            continue
                        source = f"windows-registry:{values['DisplayName'] or child_name}"
                        icon = _display_icon_path(values["DisplayIcon"])
                        if Path(icon).name.lower() in {item.lower() for item in EXECUTABLE_NAMES[tool]}:
                            yield from _candidate(icon, source)
                        install = Path(os.path.expandvars(values["InstallLocation"])) if values["InstallLocation"] else None
                        if install is None:
                            continue
                        relatives = {
                            "drawio": ("draw.io.exe", "app/draw.io.exe"),
                            "xelatex": ("miktex/bin/x64/xelatex.exe", "bin/x64/xelatex.exe", "bin/windows/xelatex.exe"),
                            "typst": ("typst.exe",),
                            "pdftoppm": ("Library/bin/pdftoppm.exe", "bin/pdftoppm.exe"),
                        }[tool]
                        for relative in relatives:
                            yield from _candidate(install / relative, source)


def _common_candidates(tool: str) -> Iterator[dict[str, str]]:
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    roaming_app_data = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
    program_roots = {
        Path(value)
        for key in ("ProgramFiles", "ProgramFiles(x86)")
        if (value := os.environ.get(key))
    }
    if os.name == "nt":
        for drive in _logical_drives():
            program_roots.add(drive / "Program Files")
            program_roots.add(drive / "Program Files (x86)")

    if tool == "xelatex":
        candidates = [
            local_app_data / "Programs/MiKTeX/miktex/bin/x64/xelatex.exe",
            roaming_app_data / "MiKTeX/miktex/bin/x64/xelatex.exe",
        ]
        for root in sorted(program_roots, key=str):
            candidates.extend((
                root / "MiKTeX/miktex/bin/x64/xelatex.exe",
                root / "MiKTeX 2.9/miktex/bin/x64/xelatex.exe",
            ))
        for drive in _logical_drives():
            texlive = drive / "texlive"
            if texlive.is_dir():
                candidates.extend(sorted(texlive.glob("*/bin/windows/xelatex.exe"), reverse=True))
    elif tool == "drawio":
        candidates = [
            local_app_data / "Programs/draw.io/draw.io.exe",
            local_app_data / "draw.io/draw.io.exe",
        ]
        candidates.extend(root / "draw.io/draw.io.exe" for root in sorted(program_roots, key=str))
    elif tool == "typst":
        candidates = [
            home / ".cargo/bin/typst.exe",
            home / "scoop/apps/typst/current/typst.exe",
            local_app_data / "Microsoft/WinGet/Links/typst.exe",
        ]
    else:
        candidates = []
        for root in sorted(program_roots, key=str):
            candidates.extend((root / "poppler/Library/bin/pdftoppm.exe", root / "poppler/bin/pdftoppm.exe"))

    for path in candidates:
        yield from _candidate(path, "common-install-location")


def resolve_tool(name: str) -> dict[str, str] | None:
    """Return an absolute executable path and discovery source, or ``None``."""

    tool = _normalise_name(name)
    seen: set[str] = set()
    override = os.environ.get(ENVIRONMENT_OVERRIDES[tool])
    streams = []
    if override:
        override_path = Path(os.path.expandvars(override)).expanduser()
        if override_path.is_dir():
            override_path = override_path / EXECUTABLE_NAMES[tool][-1]
        streams.append(_candidate(override_path, f"environment:{ENVIRONMENT_OVERRIDES[tool]}"))
    path_match = next((shutil.which(item) for item in EXECUTABLE_NAMES[tool] if shutil.which(item)), None)
    if path_match:
        streams.append(_candidate(path_match, "PATH"))
    streams.extend((_registry_candidates(tool), _common_candidates(tool)))
    for stream in streams:
        for result in stream:
            key = os.path.normcase(result["path"])
            if key not in seen:
                seen.add(key)
                result["name"] = tool
                return result
    return None


def locate_tool(name: str) -> str | None:
    """Compatibility helper returning only the executable path."""

    result = resolve_tool(name)
    return result["path"] if result else None


def tool_version(name: str, executable: str) -> str:
    args = [executable, "-v" if _normalise_name(name) == "pdftoppm" else "--version"]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            args, text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=20, creationflags=creationflags,
        )
        lines = (proc.stdout + "\n" + proc.stderr).strip().splitlines()
        return lines[0][:300] if lines else f"exit {proc.returncode}; no version text"
    except Exception as exc:  # noqa: BLE001
        return f"version unavailable: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tools", nargs="+", choices=SUPPORTED)
    parser.add_argument("--no-version", action="store_true", help="skip executable version probes")
    args = parser.parse_args()
    results: list[dict[str, str]] = []
    missing: list[str] = []
    for name in args.tools:
        result = resolve_tool(name)
        if result is None:
            missing.append(name)
            results.append({"name": name, "status": "NOT_FOUND"})
        else:
            result["status"] = "FOUND"
            if not args.no_version:
                result["version"] = tool_version(name, result["path"])
            results.append(result)
    payload = {"status": "PASS" if not missing else "FAIL", "results": results, "missing": missing}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())

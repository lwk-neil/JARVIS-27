"""Windows application discovery and launch through registered OS targets."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


_START_APPS_COMMAND = (
    "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
)
_APP_ID_RE = re.compile(r"^[A-Za-z0-9._!{}-]+$")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")


@dataclass(frozen=True)
class LaunchResult:
    accepted: bool
    method: str
    error: str = ""
    process: subprocess.Popen[bytes] | None = None


def _normalize(value: str) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def _app_names(requested: str, launcher_name: str) -> set[str]:
    names = {_normalize(requested), _normalize(launcher_name)}
    aliases = {
        "edge": {"edge", "microsoft edge", "msedge", "browser", "main browser"},
        "microsoftedge": {"edge", "microsoft edge", "msedge", "browser", "main browser"},
        "msedge": {"edge", "microsoft edge", "msedge", "browser", "main browser"},
        "browser": {"edge", "microsoft edge", "msedge", "browser", "main browser"},
        "whatsapp": {"whatsapp", "whatsapp desktop"},
    }
    for name in tuple(names):
        names.update(_normalize(alias) for alias in aliases.get(name, ()))
    return {name for name in names if name}


def _query_registered_apps() -> tuple[list[dict[str, str]], str]:
    """Read Windows' registered Start apps; the fixed command contains no user input."""
    powershell = shutil.which("powershell.exe")
    if not powershell:
        system_root = os.environ.get("WINDIR", r"C:\Windows")
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        powershell = str(candidate) if candidate.is_file() else None
    if not powershell:
        return [], "Windows PowerShell was not found; Start app registration could not be queried"

    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", _START_APPS_COMMAND],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"Start app query failed: {type(exc).__name__}: {exc}"
    if result.returncode:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        return [], f"Start app query failed: {detail}"
    try:
        value = json.loads(result.stdout.lstrip("\ufeff") or "[]")
    except json.JSONDecodeError as exc:
        return [], f"Start app query returned invalid data: {exc}"

    entries = value if isinstance(value, list) else [value]
    apps = [
        {"Name": str(item.get("Name", "")), "AppID": str(item.get("AppID", ""))}
        for item in entries if isinstance(item, dict)
    ]
    return apps, ""


def _registered_app(requested: str, launcher_name: str) -> tuple[str, str] | None:
    names = _app_names(requested, launcher_name)
    apps, query_error = _query_registered_apps()
    if query_error:
        print(f"[open_app] {query_error}")

    matches = []
    for app in apps:
        display_name = _normalize(app["Name"])
        app_id = _normalize(app["AppID"])
        if display_name in names or app_id in names:
            matches.append((display_name not in names, app["Name"], app["AppID"]))
    if not matches:
        return None
    _, name, app_id = min(matches)
    return name, app_id


def _path_on_path(names: tuple[str, ...]) -> Path | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            path = Path(resolved)
            if path.is_file():
                return path
    return None


def _app_path_registry(names: tuple[str, ...]) -> tuple[Path | None, str]:
    try:
        import winreg
    except ImportError:
        return None, "Windows registry access is unavailable"

    key_path = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    views = (
        getattr(winreg, "KEY_WOW64_64KEY", 0),
        getattr(winreg, "KEY_WOW64_32KEY", 0),
    )
    lookup_errors = []
    for name in names:
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in views:
                try:
                    with winreg.OpenKey(root, f"{key_path}\\{name}", 0,
                                        winreg.KEY_READ | view) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                    target = Path(os.path.expandvars(str(value).strip().strip('"')))
                    if target.is_file():
                        return target, ""
                    lookup_errors.append(
                        f"App Paths registered a missing executable: {target}"
                    )
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    lookup_errors.append(
                        f"App Paths lookup failed for {name}: {type(exc).__name__}: {exc}"
                    )
    return None, "; ".join(dict.fromkeys(lookup_errors))


def _known_executables(requested: str, launcher_name: str) -> tuple[Path | None, str]:
    requested_path = Path(requested.strip())
    if requested_path.is_file():
        return requested_path.resolve(), ""

    names = tuple(dict.fromkeys(
        name for name in (
            requested.strip(),
            launcher_name.strip(),
            Path(launcher_name.strip()).name,
        ) if name
    ))
    path = _path_on_path(names)
    if path:
        return path, ""

    registry_path, registry_error = _app_path_registry(names)
    if registry_path:
        return registry_path, ""

    aliases = _app_names(requested, launcher_name)
    if aliases.intersection({"edge", "microsoftedge", "msedge", "browser"}):
        roots = (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        for root in roots:
            if root:
                candidate = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                if candidate.is_file():
                    return candidate, ""
    if "whatsapp" in aliases:
        candidates = [
            Path(root) / suffix / "WhatsApp.exe"
            for root, suffix in (
                (os.environ.get("LOCALAPPDATA"), Path("Programs") / "WhatsApp"),
                (os.environ.get("LOCALAPPDATA"), Path("WhatsApp")),
                (os.environ.get("ProgramFiles"), Path("WhatsApp")),
                (os.environ.get("ProgramFiles(x86)"), Path("WhatsApp")),
            ) if root
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate, ""
    return None, registry_error


def _start_menu_shortcut(requested: str, launcher_name: str) -> Path | None:
    names = _app_names(requested, launcher_name)
    roots = (
        os.environ.get("APPDATA"),
        os.environ.get("PROGRAMDATA"),
    )
    for root in roots:
        if not root:
            continue
        programs = Path(root) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if not programs.is_dir():
            continue
        try:
            for shortcut in programs.rglob("*.lnk"):
                if _normalize(shortcut.stem) in names:
                    return shortcut
        except OSError as exc:
            print(f"[open_app] Start menu shortcut scan failed: {type(exc).__name__}: {exc}")
    return None


def _registered_uri_scheme(value: str) -> str | None:
    scheme, separator, _ = value.partition(":")
    if not separator or len(scheme) < 2 or not _URI_SCHEME_RE.fullmatch(scheme):
        return None
    if scheme.casefold() in {"file", "http", "https", "javascript", "data"}:
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, scheme) as key:
            winreg.QueryValueEx(key, "URL Protocol")
        return scheme
    except FileNotFoundError:
        return None
    except (ImportError, OSError) as exc:
        print(f"[open_app] URI registration lookup failed for {scheme}: "
              f"{type(exc).__name__}: {exc}")
        return None


def _start_registered_app(app_id: str) -> subprocess.Popen[bytes]:
    if not app_id or not _APP_ID_RE.fullmatch(app_id):
        raise ValueError("registered application identifier contains unsupported characters")
    explorer = shutil.which("explorer.exe")
    if not explorer:
        system_root = os.environ.get("WINDIR", r"C:\Windows")
        candidate = Path(system_root) / "explorer.exe"
        if candidate.is_file():
            explorer = str(candidate)
    if not explorer:
        raise FileNotFoundError("explorer.exe was not found")
    return subprocess.Popen(
        [explorer, f"shell:AppsFolder\\{app_id}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _start_executable(path: Path) -> subprocess.Popen[bytes]:
    if not path.is_file():
        raise FileNotFoundError(f"executable does not exist: {path}")
    return subprocess.Popen(
        [str(path)],
        cwd=str(path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _check_initial_exit(process: subprocess.Popen[bytes]) -> None:
    time.sleep(0.15)
    status = process.poll()
    if status not in (None, 0):
        raise RuntimeError(f"launcher process exited with status {status}")


def launch(requested: str, launcher_name: str) -> LaunchResult:
    """Request launch via a registered app, a verified executable, or a Start shortcut."""
    errors: list[str] = []

    registered = _registered_app(requested, launcher_name)
    if registered:
        display_name, app_id = registered
        try:
            process = _start_registered_app(app_id)
            _check_initial_exit(process)
            return LaunchResult(True, f"registered app ({display_name}; {app_id})",
                                process=process)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            errors.append(f"registered app activation failed: {type(exc).__name__}: {exc}")

    executable, lookup_error = _known_executables(requested, launcher_name)
    if executable:
        try:
            process = _start_executable(executable)
            _check_initial_exit(process)
            return LaunchResult(True, f"verified executable ({executable})",
                                process=process)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            errors.append(f"executable launch failed: {type(exc).__name__}: {exc}")
    elif lookup_error:
        errors.append(lookup_error)

    shortcut = _start_menu_shortcut(requested, launcher_name)
    if shortcut:
        try:
            os.startfile(str(shortcut))
            return LaunchResult(True, f"Start menu shortcut ({shortcut})")
        except (OSError, AttributeError) as exc:
            errors.append(f"Start menu shortcut launch failed: {type(exc).__name__}: {exc}")

    scheme = _registered_uri_scheme(requested.strip())
    if scheme:
        try:
            os.startfile(requested.strip())
            return LaunchResult(True, f"registered URI handler ({scheme})")
        except (OSError, AttributeError) as exc:
            errors.append(f"URI handler launch failed: {type(exc).__name__}: {exc}")

    supplied_path = Path(requested.strip())
    if ("/" in requested or "\\" in requested or requested.lower().endswith(".exe")) \
            and not supplied_path.is_file():
        errors.insert(0, f"requested executable path does not exist: {requested}")
    if not errors:
        errors.append("no matching registered app, Start menu shortcut, or executable was found")
    return LaunchResult(False, "none", "; ".join(errors))

"""
JARVIS action — open an application, and know whether it actually opened.

WHAT WAS WRONG WITH THIS FILE
    It answered "Opened Spotify." whenever its launcher returned True, and on
    Windows the launcher returned True immediately after

        subprocess.Popen(app_name, shell=True)

    which succeeds because a SHELL started — not because an application did. A
    misspelling, an app that was never installed, an installer that moved:
    every one of them produced "Opened Spotify.", said out loud, while nothing
    appeared on screen.

    The same line was also a command injection. `shutil.which(name.split(".")[0])`
    passed "notepad.exe & whoami" because `which("notepad")` succeeds, and the
    whole string then went to a shell unquoted. Verified before it was changed.

WHAT IT DOES NOW
    * No shell, anywhere. Executables are resolved to a path and started as an
      argument vector; URI schemes go through the OS handler.
    * It watches the process table for a NEW process answering to the name, and
      only says `done` when one appears. When none does, it says `unverified`
      and the assistant tells the user it could not confirm — which is true,
      and is something they can act on.
    * It answers in milliseconds and verifies behind that, so asking to open
      something no longer costs the conversation one to four seconds.

WHY IT IS NOT A LIST OF APPLICATIONS
    Windows discovery asks the machine for registered Start apps, App Paths,
    Start-menu shortcuts and verified executable locations. Other operating
    systems keep their native launchers. Verification asks the running machine
    what appeared; matching compares against whatever is running.
"""
import platform
import shutil
import subprocess
import threading
import time

from core import appidentity, outcome
from core.lazyimport import LazyModule, installed
from core import windows_app_launcher

_PYAUTOGUI = installed("pyautogui")
pyautogui = LazyModule("pyautogui")

_SYSTEM = platform.system()          # "Windows" | "Darwin" | "Linux"

# How long to keep watching for the application to appear. Chosen from the two
# ends of the range rather than the middle: a text editor is up in a fraction
# of a second, a game launcher can take ten, and a limit that suits the first
# reports the second as broken.
_LAUNCH_TIMEOUT = 12.0

# The desktop-search fallback remains for macOS and Linux, where there is no
# common registered-app activation API shared by supported desktop environments.
_SEARCH_SETTLE = 0.8
_PENDING_LOCK = threading.Lock()
_PENDING_APPS: set[str] = set()


# ─────────────────────────────────────────────────────────────────────────────
#  Per-OS launching — no shell on any path
# ─────────────────────────────────────────────────────────────────────────────
def _desktop_search(app_name: str) -> bool:
    """Use desktop search on platforms without a shared registered-app API.

    Its return value only records that the search was submitted. Process
    inspection, not this function, decides whether the application appeared.
    """
    if not _PYAUTOGUI:
        return False
    try:
        if _SYSTEM == "Darwin":
            pyautogui.hotkey("command", "space")
        else:
            pyautogui.press("win")
        time.sleep(_SEARCH_SETTLE)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(_SEARCH_SETTLE)
        pyautogui.press("enter")
        return True
    except Exception as exc:
        print(f"[open_app] desktop search failed: {exc}")
        return False


def _launch_windows(app_name: str) -> bool:
    """Compatibility wrapper for a verified Windows launch request."""
    result = windows_app_launcher.launch(app_name, app_name)
    print(f"[open_app] requested={app_name!r} method={result.method} "
          f"accepted={result.accepted}" +
          (f" reason={result.error}" if result.error else ""))
    return result.accepted


def _launch_macos(app_name: str) -> bool:
    for candidate in (app_name, f"{app_name}.app"):
        try:
            result = subprocess.run(
                ["open", "-a", candidate], capture_output=True, timeout=8
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen(
                [binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            pass

    return _desktop_search(app_name)


_LINUX_TERMINALS = [
    "x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal",
    "xterm", "lxterminal", "mate-terminal", "tilix", "alacritty", "kitty",
]


def _launch_linux(app_name: str) -> bool:
    # "terminal" means whichever one this distribution actually ships.
    if app_name in ("x-terminal-emulator", "gnome-terminal", "terminal"):
        for term in _LINUX_TERMINALS:
            path = shutil.which(term)
            if not path:
                continue
            try:
                subprocess.Popen(
                    [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                continue

    binary = (
        shutil.which(app_name)
        or shutil.which(app_name.lower())
        or shutil.which(app_name.lower().replace(" ", "-"))
        or shutil.which(app_name.lower().replace(" ", "_"))
    )
    if binary:
        try:
            subprocess.Popen(
                [binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            pass

    for name in (
        app_name.lower(),
        app_name.lower().replace(" ", "-"),
        app_name.lower().replace(" ", ""),
    ):
        try:
            result = subprocess.run(
                ["gtk-launch", name], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            break
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["xdg-open", app_name], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    return _desktop_search(app_name)


_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin": _launch_macos,
    "Linux": _launch_linux,
}


# ─────────────────────────────────────────────────────────────────────────────
#  HUD helpers — no-ops without a player, exactly as the whatsapp plugins do
# ─────────────────────────────────────────────────────────────────────────────
def _log(player, message: str) -> None:
    if player:
        try:
            player.write_log(message)
        except Exception:
            pass


def _say(player, instruction: str) -> None:
    if player and hasattr(player, "request_say"):
        try:
            player.request_say(instruction)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Launch + verify, off the conversation's thread
# ─────────────────────────────────────────────────────────────────────────────
def _launch_and_verify(player, spoken: str, launcher_name: str,
                       before: set[int], existing: list, pending_key: str) -> None:
    """The part that takes seconds. Speaks ONLY when something needs saying.

    Silence means it worked: the window is on the user's screen and a second
    announcement over the top of it is noise — the same reasoning
    whatsapp_call.py applies to a phone that is already ringing.
    """
    try:
        if _SYSTEM == "Windows":
            launch_result = windows_app_launcher.launch(spoken, launcher_name)
            requested = launch_result.accepted
            method = launch_result.method
            launch_error = launch_result.error
            launch_process = launch_result.process
            print(f"[open_app] requested={spoken!r} method={method} "
                  f"accepted={requested}" +
                  (f" reason={launch_error}" if launch_error else ""))
        else:
            launcher = _LAUNCHERS[_SYSTEM]
            requested = launcher(launcher_name)
            if not requested and launcher_name.lower() != spoken.lower():
                requested = launcher(spoken)
            method = "platform launcher"
            launch_error = ""
            launch_process = None

        if not requested:
            trouble = f"{spoken} could not be started: {launch_error or 'no supported application target was found'}"
            _log(player, f"JARVIS: {trouble}")
            _say(player, "Tell the user, in one short sentence in their own "
                         f"language: {trouble}")
            return

        for candidate in existing[:8]:
            if appidentity.focus(candidate):
                _log(player, f"JARVIS: {candidate.label} brought to the front.")
                return

        appeared = appidentity.wait_for_launch(
            spoken, before, timeout=_LAUNCH_TIMEOUT
        )
        if appeared is not None:
            _log(player, f"JARVIS: {appeared.label} is open.")
            return

        try:
            exit_status = launch_process.poll() if launch_process is not None else None
        except OSError as exc:
            exit_status = f"unavailable ({type(exc).__name__}: {exc})"
        status_detail = (f"; launcher process exit status={exit_status}"
                         if exit_status is not None else "")
        trouble = (f"{spoken} launch was accepted via {method}, but no new "
                   f"application appeared within {int(_LAUNCH_TIMEOUT)} seconds, "
                   "so it is not confirmed open; it may still be loading or "
                   f"may not expose a detectable process{status_detail}")

        _log(player, f"JARVIS: {trouble}")
        _say(player, "Tell the user, in one short sentence in their own "
                     f"language: {trouble}")
    except Exception as exc:
        print(f"[open_app] requested={spoken!r} method=unknown "
              f"failure={type(exc).__name__}: {exc}")
        _say(player, "Tell the user, in one short sentence in their own "
                     f"language: opening {spoken} failed - {exc}")
    finally:
        with _PENDING_LOCK:
            _PENDING_APPS.discard(pending_key)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def open_app(parameters=None, response=None, player=None,
             session_memory=None) -> str:
    spoken = ((parameters or {}).get("app_name") or "").strip()
    if not spoken:
        return outcome.failed("open_app", "no application name was given")

    if _SYSTEM not in _LAUNCHERS:
        return outcome.failed(
            "open_app", f"this operating system ({_SYSTEM}) is not supported",
            app=spoken,
        )

    # Already open? Then there is nothing to launch and nothing to wait for,
    # and saying so is more useful than a second copy. This is also the one
    # branch that can answer `done` immediately, because the evidence is
    # already in hand rather than somewhere in the next ten seconds.
    #
    # include_self, unlike the close path, and for the opposite reason. There
    # the assistant's own processes must never be a TARGET; here the question
    # is only "is this already running", and it is already running whether the
    # process belongs to us or not. Without this, asking to open the very
    # application the assistant lives inside reports `started` and goes off to
    # launch a second copy of it — seen exactly that way, against a packaged
    # build whose siblings the close guard had just learnt to protect.
    existing = appidentity.running(spoken, include_self=True)
    if existing:
        best = existing[0]
        # ALREADY RUNNING IS NOT ALREADY DONE.
        #
        # This branch used to report "it was already open" and stop. That is
        # true and useless: an application running behind three other windows
        # is not on the user's screen, nothing changed when they asked, and
        # from where they are sitting the assistant did not open anything.
        # Reported as a bug in exactly those words — "it does not even open
        # applications" — with WhatsApp and Edge both running in the tray.
        #
        # Clicking a taskbar icon for a running app raises its window. So does
        # this. When there is no window to raise — a background service, or an
        # app that has gone to the tray — focus() says so and the launcher runs
        # below, which is what brings a tray app back.
        # Try every candidate, not just the best-scoring one.
        #
        # A modern application is many processes and only one of them owns the
        # window. Ranking puts the exact name match first, and on Windows that
        # is routinely a background service: measured here, `WhatsApp` and
        # `msedge` both scored 100 on processes with no window at all, so
        # focusing "the best match" focused nothing and the branch gave up.
        #
        # Store apps are the harder half of the same thing — their window
        # belongs to ApplicationFrameHost, not to the app's own process — which
        # is why activation is retried through the registered app target below.
        for candidate in existing[:8]:
            if appidentity.focus(candidate):
                _log(player, f"JARVIS: {candidate.label} brought to the front.")
                return outcome.done(
                    "open_app", app=spoken, matched=candidate.label,
                    already_running=True, focused=True, verified=True,
                )
        print(f"[open_app] {best.label} is running but no window could be "
              f"raised — launching it instead, which is what brings back an "
              f"app that is only in the tray.")

    launcher_name = appidentity.launcher_name(spoken)
    before = appidentity.snapshot()
    pending_key = appidentity.fold(launcher_name) or appidentity.fold(spoken)
    with _PENDING_LOCK:
        if pending_key in _PENDING_APPS:
            return outcome.started("open_app", app=spoken, duplicate_request=True)
        _PENDING_APPS.add(pending_key)

    _log(player, f"JARVIS: Opening {spoken}…")

    try:
        threading.Thread(
            target=_launch_and_verify,
            args=(player, spoken, launcher_name, before, existing, pending_key),
            daemon=True, name=f"open-app-{spoken[:20]}",
        ).start()
    except RuntimeError as exc:
        with _PENDING_LOCK:
            _PENDING_APPS.discard(pending_key)
        _log(player, f"JARVIS: Could not schedule {spoken}: {exc}")
        return outcome.failed(
            "open_app", f"background launch could not be scheduled: {type(exc).__name__}: {exc}",
            app=spoken,
        )

    # Facts, not a sentence. Handing the model a finished English sentence is
    # an invitation to repeat it verbatim — whatsapp_call.py has the receipt:
    # a request made in Turkish came back in English, padded with an offer
    # nobody had made. The model writes the sentence, in the user's language.
    return outcome.started("open_app", app=spoken)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_app",
    "description": (
        "Opens an application on this computer. Use whenever the user asks to "
        "open, launch or start any app or program. Put the application's name "
        "in 'app_name' exactly as the user said it. "
        "This tool answers immediately and confirms the launch in the "
        "background: on status=started say only that it is opening, never that "
        "it is open. If it does not appear, you will be told separately - "
        "relay that plainly rather than claiming success. Never say you opened "
        "something without calling this tool. "
        "To CLOSE an application use computer_control with action='close_app', "
        "not this tool. "
        "DO NOT use this tool to reach a WEB PAGE. 'open Chrome and go to "
        "YouTube', 'open YouTube', 'search the web' are all browser_control "
        "alone - it opens the browser itself. Calling open_app for the browser "
        "first and browser_control after it launches the browser TWICE, the "
        "second copy on a different profile, which is what puts a 'Who's using "
        "Chrome?' picker on the screen. Use this tool only when the user wants "
        "the application and nothing in it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": (
                    "The application's REAL name, not the user's shorthand. "
                    "Expand abbreviations and nicknames before passing them: "
                    "'wp' or 'whats' is 'WhatsApp', 'ig' is 'Instagram', 'vs "
                    "code' is 'Visual Studio Code'. A two-letter fragment "
                    "matches the wrong program - 'wp' finds WPS Office. Any "
                    "application on the machine works; there is no fixed list."
                ),
            }
        },
        "required": ["app_name"],
    },
    "handler": open_app,
}

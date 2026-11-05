# PyInstaller one-file Windows build. Runtime configuration stays beside the
# executable; only the resources discovered from disk are bundled here.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

datas = [
    (str(ROOT / "core" / "face_model.obj"), "core"),
    (str(ROOT / "core" / "prompt.txt"), "core"),
    (str(ROOT / "config" / "syke.ico"), "config"),
    (str(ROOT / "config" / "syke.png"), "config"),
    (str(ROOT / "config" / "syke_spider_swing.png"), "config"),
    (str(ROOT / "dashboard" / "static"), "dashboard/static"),
    (str(ROOT / "browser_extension"), "browser_extension"),
]
for folder in ("actions", "plugins"):
    datas.extend(
        (str(path), folder)
        for path in (ROOT / folder).glob("*.py")
    )

hiddenimports = (
    collect_submodules("actions")
    + collect_submodules("plugins")
    + collect_submodules("providers")
)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SYKE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "config" / "syke.ico"),
)

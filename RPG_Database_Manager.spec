# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for RPG Database Manager (Windows and Linux, onedir).
Build:  pyinstaller --noconfirm RPG_Database_Manager.spec
Output: dist/RPG_Database_Manager/ (Windows)  or  dist/rpg-database-manager/ (Linux),
containing the application.
Linux AppImage: packaging/linux/build_appimage.sh
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_submodules

project_root = Path(SPECPATH).absolute()  # independent of the directory pyinstaller is started from
IS_WINDOWS = sys.platform == 'win32'
APP_NAME = 'RPG_Database_Manager' if IS_WINDOWS else 'rpg-database-manager'
_ico = project_root / 'data' / 'icons' / 'app_icon.ico'  # generated from the PNG by the build workflow
ICON = str(_ico) if IS_WINDOWS and _ico.exists() else None

datas = [(str(project_root / 'data'), 'data'), (str(project_root / 'README.md'), '.'),
         (str(project_root / 'LICENSE'), '.'),
         # Help > Guides reads these (and offers to save copies of them)
         (str(project_root / 'docs' / 'html_module_guide.md'), 'docs'),
         (str(project_root / 'tools' / 'html_module' / 'module_template.html'), 'tools/html_module'),
         (str(project_root / 'docs' / 'entity_file_guide.md'), 'docs'),
         (str(project_root / 'tools' / 'entity_files' / 'entities_template.md'), 'tools/entity_files'),
         (str(project_root / 'tools' / 'entity_files' / 'entities_template.json'), 'tools/entity_files')]
binaries = []
hiddenimports = ['PIL', 'cryptography']
# keyring picks its backend at runtime (Secret Service / KWallet / Windows / macOS), so bundle them all
for _pkg in ('keyring.backends', 'secretstorage', 'jeepney', 'win32ctypes'):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception as e:
        print(f"WARNING: could not collect {_pkg}: {e}")


def _optional(pkg):
    """Bundle an optional dependency completely, if it is installed."""
    try:
        d, b, h = collect_all(pkg)
    except Exception as e:
        print(f"WARNING: could not bundle optional package {pkg}: {e}")
        return
    datas.extend(d); binaries.extend(b); hiddenimports.extend(h)


for _pkg in ('pyaudio', 'speech_recognition', 'faster_whisper', 'ctranslate2', 'onnxruntime', 'av', 'tokenizers'):
    _optional(_pkg)

_excludes = [
    'PySide6', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore',
    'torch', 'torchvision', 'torchaudio', 'transformers', 'matplotlib',
    'pandas', 'scipy', 'IPython', 'notebook', 'tkinter',
    # NOTE: numpy is intentionally NOT excluded (needed by ctranslate2/faster-whisper)
]

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=_excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=APP_NAME,
    icon=ICON,
    console=False,
    upx=False,  # UPX can corrupt Qt libraries
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)

"""Build a standalone Windows application, including its Qt runtime."""
from pathlib import Path
import subprocess
import sys
import shutil
from PIL import Image, ImageDraw

base = Path(__file__).resolve().parent
icon = Image.new('RGBA', (256, 256), '#0b101b')
d = ImageDraw.Draw(icon)
d.ellipse((36, 36, 220, 220), outline='#b8f575', width=12)
d.ellipse((52, 47, 176, 209), fill='#b8f575')
d.ellipse((87, 38, 208, 197), fill='#0b101b')
icon.save(base / 'orbit.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed', '--onedir', '--distpath', str(base / 'release'), '--name', 'Orbit', '--icon', str(base / 'orbit.ico'), '--add-data', f'{base / "index.html"};.', '--add-data', f'{base / "features.js"};.', '--add-data', f'{base / "features.css"};.', '--add-data', f'{base / "orbit.ico"};.', '--exclude-module', 'PyQt6', '--exclude-module', 'PyQt5', str(base / 'launcher.py')], cwd=base, check=True)
# Qt uses Windows' ICU API. A different ICU on PATH can be collected by
# PyInstaller even though it lacks the unversioned exports Qt requires.
# Let Windows resolve its own system DLL instead of bundling that conflict.
runtime = base / 'release/Orbit/_internal'
(runtime / 'icuuc.dll').unlink(missing_ok=True)
import PySide6
for dll in Path(PySide6.__file__).parent.glob('vcruntime140*.dll'):
    shutil.copy2(dll, runtime / dll.name)

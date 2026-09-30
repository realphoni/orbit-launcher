"""Build the portable Orbit Windows application."""

from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "release"
APP_DIR = RELEASE_DIR / "Orbit"
ICON_PATH = ROOT / "orbit.ico"
PYINSTALLER_DATA = ("index.html", "features.js", "features.css", "orbit.ico")


def create_icon(path: Path) -> None:
    """Create the multi-resolution Orbit crescent icon."""
    icon = Image.new("RGBA", (256, 256), "#0b101b")
    painter = ImageDraw.Draw(icon)
    painter.ellipse((36, 36, 220, 220), outline="#b8f575", width=12)
    painter.ellipse((52, 47, 176, 209), fill="#b8f575")
    painter.ellipse((87, 38, 208, 197), fill="#0b101b")
    icon.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def pyinstaller_command() -> list[str]:
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
        "--distpath", str(RELEASE_DIR), "--name", "Orbit", "--icon", str(ICON_PATH),
    ]
    for filename in PYINSTALLER_DATA:
        command.extend(("--add-data", f"{ROOT / filename};."))
    command.extend(("--exclude-module", "PyQt6", "--exclude-module", "PyQt5", str(ROOT / "launcher.py")))
    return command


def fix_qt_runtime(runtime_dir: Path) -> None:
    """Remove a conflicting ICU copy and align the bundled VC runtime with Qt."""
    (runtime_dir / "icuuc.dll").unlink(missing_ok=True)
    import PySide6
    for runtime_dll in Path(PySide6.__file__).parent.glob("vcruntime140*.dll"):
        shutil.copy2(runtime_dll, runtime_dir / runtime_dll.name)


def main() -> None:
    create_icon(ICON_PATH)
    subprocess.run(pyinstaller_command(), cwd=ROOT, check=True)
    fix_qt_runtime(APP_DIR / "_internal")
    print(f"Portable app built at {APP_DIR}")


if __name__ == "__main__":
    main()

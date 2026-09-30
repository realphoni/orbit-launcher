"""Build a self-contained OrbitSetup.exe with the portable app embedded."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE_APP = ROOT / "release" / "Orbit"
OUTPUT_DIRECTORY = ROOT / "release" / "installer"
PRIVATE_PAYLOAD_FOLDERS = {"data", "assets"}


def copy_clean_payload(destination: Path) -> None:
    if not (SOURCE_APP / "Orbit.exe").exists():
        raise FileNotFoundError("Build Orbit with build.py before building the installer.")

    def ignore(directory: str, names: list[str]) -> set[str]:
        return PRIVATE_PAYLOAD_FOLDERS.intersection(names) if Path(directory) == SOURCE_APP else set()

    shutil.copytree(SOURCE_APP, destination / "Orbit", ignore=ignore)


def create_splash(path: Path) -> None:
    """Create the immediate extraction splash shown before Qt is unpacked."""
    image = Image.new("RGB", (560, 300), "#080d15")
    painter = ImageDraw.Draw(image)
    painter.rounded_rectangle((2, 2, 557, 297), radius=28, fill="#111b29", outline="#2e4054", width=2)
    painter.ellipse((54, 55, 194, 195), outline="#b8f575", width=6)
    painter.ellipse((74, 75, 174, 175), fill="#b8f575")
    painter.ellipse((112, 64, 190, 165), fill="#111b29")
    try:
        title_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 36)
        copy_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 17)
        tiny_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 13)
    except OSError:
        title_font = copy_font = tiny_font = ImageFont.load_default()
    painter.text((235, 76), "O R B I T", font=title_font, fill="#f7faff")
    painter.text((237, 132), "Preparing a beautiful setup…", font=copy_font, fill="#b8f575")
    painter.text((237, 165), "Unpacking the launcher and its runtime", font=tiny_font, fill="#91a0b7")
    painter.rounded_rectangle((55, 235, 505, 243), radius=4, fill="#243246")
    painter.rounded_rectangle((55, 235, 350, 243), radius=4, fill="#b8f575")
    image.save(path)


def write_spec(spec_path: Path, payload: Path, splash: Path) -> None:
    """Write a one-file spec that avoids the incompatible ICU DLL found on this PC."""
    spec_path.write_text(
        f'''# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    [{str(ROOT / "installer.py")!r}],
    pathex=[],
    binaries=[],
    datas=[({str(payload)!r}, "payload"), ({str(ROOT / "orbit.ico")!r}, ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=["PyQt6"],
    noarchive=False,
    optimize=0,
)
a.binaries = [entry for entry in a.binaries if entry[0].lower() != "icuuc.dll"]
pyz = PYZ(a.pure)
splash = Splash(
    {str(splash)!r},
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    minify_script=True,
    always_on_top=True,
)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    [],
    name="OrbitSetup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon={str(ROOT / "orbit.ico")!r},
)
''',
        encoding="utf-8",
    )


def build() -> Path:
    with tempfile.TemporaryDirectory(prefix="orbit-installer-", dir=ROOT) as temporary:
        temporary_path = Path(temporary)
        payload = temporary_path / "payload"
        splash = temporary_path / "splash.png"
        spec = temporary_path / "OrbitSetup.spec"
        copy_clean_payload(payload)
        create_splash(splash)
        write_spec(spec, payload, splash)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(OUTPUT_DIRECTORY), str(spec),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
    output = OUTPUT_DIRECTORY / "OrbitSetup.exe"
    print(f"Installer built at {output}")
    return output


if __name__ == "__main__":
    build()

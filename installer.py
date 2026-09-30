"""Native Windows installer for the Orbit Legacy game launcher.

Run this file during development after ``build.py``. The packaged installer
embeds the same ``release/Orbit`` payload under ``payload/Orbit``.
"""

from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)


PRODUCT_NAME = "Orbit Legacy"
APP_DIRECTORY_NAME = "Orbit"
EXECUTABLE_NAME = "Orbit.exe"
ROOT = Path(__file__).resolve().parent
PRESERVED_FOLDERS = ("data", "assets")


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", ROOT))


def payload_directory() -> Path:
    embedded = bundle_root() / "payload" / APP_DIRECTORY_NAME
    return embedded if embedded.exists() else ROOT / "release" / APP_DIRECTORY_NAME


def default_install_directory() -> Path:
    local_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    # Keep the original folder so Orbit installs upgrade in place and retain data.
    return local_data / "Programs" / APP_DIRECTORY_NAME


def validate_payload(payload: Path) -> None:
    if not (payload / EXECUTABLE_NAME).is_file() or not (payload / "_internal").is_dir():
        raise FileNotFoundError(
            "The Orbit Legacy app payload is missing. Run build.py before the source installer, "
            "or rebuild OrbitLegacySetup.exe."
        )


def packaging_splash_is_alive() -> bool:
    """Report whether the optional PyInstaller extraction splash is visible."""
    try:
        import pyi_splash
    except ImportError:
        return False
    return pyi_splash.is_alive()


def close_packaging_splash() -> None:
    """Close PyInstaller's extraction splash once the Qt window has rendered."""
    if packaging_splash_is_alive():
        import pyi_splash
        pyi_splash.close()


def validate_install_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
        raise ValueError("Choose a folder inside a drive, not the drive itself.")
    return resolved


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def human_size(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{int(amount)} B" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return "0 B"


def create_shortcut(shortcut: Path, executable: Path) -> None:
    """Create a shell link without interpolating paths into the command."""
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        ORBIT_LINK=str(shortcut), ORBIT_EXE=str(executable), ORBIT_DIR=str(executable.parent)
    )
    script = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut($env:ORBIT_LINK);"
        "$s.TargetPath=$env:ORBIT_EXE;"
        "$s.WorkingDirectory=$env:ORBIT_DIR;"
        "$s.IconLocation=$env:ORBIT_EXE+',0';"
        "$s.Description='Open Orbit Legacy Game Launcher';$s.Save()"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class InstallWorker(QThread):
    progress_changed = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, source: Path, target: Path, desktop: bool, start_menu: bool) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.desktop = desktop
        self.start_menu = start_menu

    def run(self) -> None:
        stage = self.target.parent / f".orbit-stage-{uuid.uuid4().hex}"
        backup = self.target.parent / f".orbit-backup-{uuid.uuid4().hex}"
        try:
            self._copy_app(stage)
            self._preserve_library(stage)
            self._activate(stage, backup)
            self._create_shortcuts()
            self.progress_changed.emit(100, "Orbit Legacy is ready for launch")
            self.succeeded.emit(str(self.target / EXECUTABLE_NAME))
        except Exception as error:
            self._recover(stage, backup)
            self.failed.emit(str(error))

    def _copy_app(self, stage: Path) -> None:
        files = [path for path in self.source.rglob("*") if path.is_file()]
        total = max(sum(path.stat().st_size for path in files), 1)
        copied = 0
        stage.mkdir(parents=True)
        for source_file in files:
            relative = source_file.relative_to(self.source)
            if relative.parts and relative.parts[0] in PRESERVED_FOLDERS:
                continue
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
            copied += source_file.stat().st_size
            self.progress_changed.emit(min(82, int(copied / total * 82)), f"Polishing {relative.name}")

    def _preserve_library(self, stage: Path) -> None:
        self.progress_changed.emit(87, "Preserving your library and artwork")
        for name in PRESERVED_FOLDERS:
            current = self.target / name
            if current.exists():
                shutil.copytree(current, stage / name, dirs_exist_ok=True)

    def _activate(self, stage: Path, backup: Path) -> None:
        self.progress_changed.emit(92, "Sliding Orbit Legacy into place")
        self.target.parent.mkdir(parents=True, exist_ok=True)
        if self.target.exists():
            self.target.replace(backup)
        stage.replace(self.target)
        if backup.exists():
            shutil.rmtree(backup)

    def _create_shortcuts(self) -> None:
        self.progress_changed.emit(97, "Finishing the Windows experience")
        executable = self.target / EXECUTABLE_NAME
        if self.desktop:
            create_shortcut(Path.home() / "Desktop" / f"{PRODUCT_NAME}.lnk", executable)
        if self.start_menu:
            app_data = Path(os.environ["APPDATA"])
            create_shortcut(app_data / f"Microsoft/Windows/Start Menu/Programs/{PRODUCT_NAME}.lnk", executable)

    def _recover(self, stage: Path, backup: Path) -> None:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if backup.exists() and not self.target.exists():
            backup.replace(self.target)


class OrbitMark(QWidget):
    """Animated crescent logo with a softly orbiting satellite."""

    def __init__(self) -> None:
        super().__init__()
        self._phase = 0.0
        self.setFixedSize(132, 132)
        self.animation = QPropertyAnimation(self, b"phase", self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(3200)
        self.animation.setLoopCount(-1)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.start()

    def get_phase(self) -> float:
        return self._phase

    def set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = Property(float, get_phase, set_phase)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        painter.setPen(QPen(QColor(184, 245, 117, 30 + int(self._phase * 24)), 18))
        painter.drawEllipse(center, 43, 43)
        painter.setPen(QPen(QColor("#b8f575"), 4))
        painter.drawEllipse(center, 43, 43)

        moon = QPainterPath()
        moon.addEllipse(center, 32, 32)
        cutout = QPainterPath()
        cutout.addEllipse(QPointF(center.x() + 13, center.y() - 6), 29, 29)
        painter.fillPath(moon.subtracted(cutout), QColor("#b8f575"))

        angle = self._phase * math.tau
        satellite = QPointF(center.x() + 43 * math.cos(angle), center.y() + 43 * math.sin(angle))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#f3ffd9"))
        painter.drawEllipse(satellite, 4.5, 4.5)


class InstallerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.payload = payload_directory()
        self.worker: InstallWorker | None = None
        self.installed_executable: Path | None = None
        self.setWindowTitle(f"{PRODUCT_NAME} Setup")
        self.setWindowIcon(QIcon(str(bundle_root() / "orbit.ico")))
        self.setFixedSize(840, 570)
        self.setObjectName("window")
        self._build_ui()
        self._apply_style()
        self._add_shadow(self.card)

    def _build_ui(self) -> None:
        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(28, 28, 28, 28)
        shell_layout.setSpacing(0)
        self.card = QFrame(objectName="card")
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self._brand_panel())
        self.pages = QStackedWidget(objectName="pages")
        self.pages.addWidget(self._welcome_page())
        self.pages.addWidget(self._progress_page())
        self.pages.addWidget(self._finish_page())
        card_layout.addWidget(self.pages, 1)
        shell_layout.addWidget(self.card)
        self.setCentralWidget(shell)

    def _brand_panel(self) -> QWidget:
        panel = QFrame(objectName="brandPanel")
        panel.setFixedWidth(290)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(12)
        layout.addWidget(OrbitMark(), alignment=Qt.AlignmentFlag.AlignHCenter)
        name = QLabel("O R B I T", objectName="brandName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        edition = QLabel("L E G A C Y", objectName="editionName")
        edition.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(edition)
        tagline = QLabel("YOUR GAMES.\nONE BEAUTIFUL PLACE.", objectName="tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)
        layout.addStretch()
        layout.addWidget(QLabel("● Local-first library\n● Controller-friendly\n● Your data stays yours", objectName="featureList"))
        return panel

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(42, 42, 42, 36)
        layout.setSpacing(14)
        layout.addWidget(QLabel(title, objectName="heading"))
        layout.addWidget(QLabel(subtitle, objectName="subtitle"))
        layout.addSpacing(18)
        return page, layout

    def _welcome_page(self) -> QWidget:
        page, layout = self._page("Ready for liftoff?", "Set up Orbit Legacy in a few smooth seconds.")
        layout.addWidget(QLabel("INSTALL LOCATION", objectName="fieldLabel"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(default_install_directory()), objectName="pathEdit")
        browse = QPushButton("Browse", objectName="ghostButton")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        layout.addLayout(path_row)
        try:
            size_copy = f"About {human_size(directory_size(self.payload))} · upgrades preserve ratings, notes, and artwork"
        except OSError:
            size_copy = "Upgrades preserve ratings, notes, and artwork"
        layout.addWidget(QLabel(size_copy, objectName="hint"))
        layout.addSpacing(8)
        self.desktop_shortcut = QCheckBox("Add a desktop shortcut")
        self.desktop_shortcut.setChecked(True)
        self.start_shortcut = QCheckBox("Add Orbit Legacy to the Start menu")
        self.start_shortcut.setChecked(True)
        layout.addWidget(self.desktop_shortcut)
        layout.addWidget(self.start_shortcut)
        layout.addStretch()
        self.install_button = QPushButton("Install Orbit Legacy  →", objectName="primaryButton")
        self.install_button.setMinimumHeight(52)
        self.install_button.clicked.connect(self._start_install)
        layout.addWidget(self.install_button)
        return page

    def _progress_page(self) -> QWidget:
        page, layout = self._page("Making it yours", "Orbit Legacy is settling into Windows.")
        layout.addStretch()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        layout.addWidget(self.progress)
        self.progress_label = QLabel("Preparing the cabin…", objectName="progressLabel")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)
        self.percent_label = QLabel("0%", objectName="percentLabel")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.percent_label)
        layout.addStretch()
        return page

    def _finish_page(self) -> QWidget:
        page, layout = self._page("That was silky.", "Orbit Legacy is installed and ready to play.")
        layout.addStretch()
        badge = QLabel("✓", objectName="successBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(84, 84)
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.finish_path = QLabel(objectName="hint")
        self.finish_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.finish_path.setWordWrap(True)
        layout.addWidget(self.finish_path)
        self.launch_after = QCheckBox("Launch Orbit Legacy now")
        self.launch_after.setChecked(True)
        layout.addWidget(self.launch_after, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        done = QPushButton("Finish", objectName="primaryButton")
        done.setMinimumHeight(52)
        done.clicked.connect(self._finish)
        layout.addWidget(done)
        return page

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose where Orbit Legacy should live", self.path_edit.text())
        if folder:
            self.path_edit.setText(str(Path(folder) / APP_DIRECTORY_NAME))

    def _start_install(self) -> None:
        try:
            validate_payload(self.payload)
            destination = validate_install_directory(Path(self.path_edit.text()))
        except (FileNotFoundError, ValueError) as error:
            QMessageBox.warning(self, "Orbit Legacy needs a little help", str(error))
            return
        self.pages.setCurrentIndex(1)
        self.install_button.setEnabled(False)
        self.worker = InstallWorker(
            self.payload, destination, self.desktop_shortcut.isChecked(), self.start_shortcut.isChecked()
        )
        self.worker.progress_changed.connect(self._update_progress)
        self.worker.succeeded.connect(self._complete)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _update_progress(self, value: int, message: str) -> None:
        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")
        self.progress_label.setText(message)

    def _complete(self, executable: str) -> None:
        self.installed_executable = Path(executable)
        self.finish_path.setText(f"Installed at\n{self.installed_executable.parent}")
        self.pages.setCurrentIndex(2)

    def _failed(self, message: str) -> None:
        self.pages.setCurrentIndex(0)
        self.install_button.setEnabled(True)
        QMessageBox.critical(
            self, "Orbit Legacy could not be installed",
            message + "\n\nIf Orbit Legacy is open, close it and try again. Your previous installation was preserved.",
        )

    def _finish(self) -> None:
        if self.launch_after.isChecked() and self.installed_executable:
            try:
                subprocess.Popen([str(self.installed_executable)], cwd=self.installed_executable.parent)
            except OSError as error:
                QMessageBox.warning(self, "Orbit Legacy is installed", f"Orbit Legacy could not be opened:\n{error}")
        QApplication.quit()

    @staticmethod
    def _add_shadow(widget: QWidget) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(42)
        shadow.setOffset(0, 15)
        shadow.setColor(QColor(0, 0, 0, 125))
        widget.setGraphicsEffect(shadow)

    def _apply_style(self) -> None:
        self.setStyleSheet(STYLESHEET)


STYLESHEET = """
QMainWindow#window { background: #070b12; }
QFrame#card { background: #111927; border: 1px solid #273348; border-radius: 22px; }
QFrame#brandPanel { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #172839,stop:.55 #10251f,stop:1 #0b111c); border-top-left-radius:22px; border-bottom-left-radius:22px; }
QStackedWidget#pages { background:#111927; border-top-right-radius:22px; border-bottom-right-radius:22px; }
QLabel { color:#f6f8ff; font-family:"Segoe UI"; }
QLabel#brandName { font-size:24px; font-weight:800; letter-spacing:6px; }
QLabel#editionName { color:#91a0b7; font-size:9px; font-weight:700; letter-spacing:4px; }
QLabel#tagline { color:#b8f575; font-size:11px; font-weight:700; letter-spacing:2px; }
QLabel#featureList { color:#9cabbe; font-size:12px; }
QLabel#heading { font-size:31px; font-weight:750; }
QLabel#subtitle { color:#94a3b8; font-size:14px; }
QLabel#fieldLabel { color:#b8f575; font-size:10px; font-weight:700; letter-spacing:2px; }
QLabel#hint { color:#7f8da3; font-size:11px; }
QLabel#progressLabel { color:#dce6f4; font-size:14px; margin-top:18px; }
QLabel#percentLabel { color:#b8f575; font-size:25px; font-weight:800; }
QLabel#successBadge { color:#14200c; background:#b8f575; border-radius:42px; font-size:38px; font-weight:900; }
QLineEdit#pathEdit { color:#eef4ff; background:#0a101a; border:1px solid #2b394f; border-radius:10px; padding:13px 14px; selection-background-color:#7bbf45; }
QLineEdit#pathEdit:focus { border-color:#b8f575; }
QPushButton { color:#e9eff8; font-family:"Segoe UI"; font-weight:600; border-radius:10px; padding:11px 17px; }
QPushButton#ghostButton { background:#1c2738; border:1px solid #34435a; }
QPushButton#ghostButton:hover { background:#27354a; border-color:#5c728e; }
QPushButton#primaryButton { color:#14200c; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #a8ee66,stop:.55 #c7ff8d,stop:1 #94df55); border:1px solid #d8ffad; font-size:14px; font-weight:800; }
QPushButton#primaryButton:hover { background:#d2ffa2; }
QPushButton#primaryButton:pressed { background:#91d755; padding-top:13px; }
QCheckBox { color:#c3cede; font-family:"Segoe UI"; spacing:10px; padding:4px; }
QCheckBox::indicator { width:18px; height:18px; border:1px solid #42536c; border-radius:5px; background:#0a101a; }
QCheckBox::indicator:checked { background:#b8f575; border-color:#d8ffad; }
QProgressBar { background:#090e17; border:1px solid #263248; border-radius:6px; }
QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6db83f,stop:.5 #b8f575,stop:1 #e1ffbd); border-radius:5px; }
"""


def main() -> int:
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Phoni.OrbitLegacy.Installer")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(f"{PRODUCT_NAME} Setup")
    app.setFont(QFont("Segoe UI", 10))
    window = InstallerWindow()
    window.show()
    # Force the first Qt paint before removing PyInstaller's extraction splash.
    app.processEvents()
    close_packaging_splash()
    if "--smoke-test" in sys.argv:
        def capture_and_exit() -> None:
            output = Path(sys.executable).resolve().parent / "installer-smoke.png"
            window.grab().save(str(output))
            app.exit(2 if packaging_splash_is_alive() else 0)

        QTimer.singleShot(1200, capture_and_exit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

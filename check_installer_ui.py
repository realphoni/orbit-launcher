"""Render each installer state for a quick visual smoke test."""

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from installer import InstallerWindow


app = QApplication(sys.argv)
window = InstallerWindow()
window.show()


def capture() -> None:
    output = Path(__file__).with_name("installer-preview.png")
    window.grab().save(str(output))
    print(output)
    app.quit()


QTimer.singleShot(1200, capture)
raise SystemExit(app.exec())

import tempfile
from pathlib import Path
import unittest

from build_installer import create_splash
from installer import InstallWorker, human_size, validate_install_directory, validate_payload


class InstallerTests(unittest.TestCase):
    def test_payload_requires_executable_and_runtime(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            payload = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                validate_payload(payload)
            (payload / "Orbit.exe").touch()
            (payload / "_internal").mkdir()
            validate_payload(payload)

    def test_install_directory_rejects_drive_root(self):
        with self.assertRaises(ValueError):
            validate_install_directory(Path("I:/"))
        self.assertEqual(validate_install_directory(Path("I:/Apps/Orbit")).name, "Orbit")

    def test_human_size_is_readable(self):
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")

    def test_upgrade_preserves_user_library(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            source = root / "source"
            target = root / "installed" / "Orbit"
            (source / "_internal").mkdir(parents=True)
            (source / "Orbit.exe").write_bytes(b"new app")
            (source / "_internal/runtime.dll").write_bytes(b"runtime")
            (source / "data").mkdir()
            (source / "data/settings.json").write_text("payload should not win")
            (target / "data").mkdir(parents=True)
            (target / "data/settings.json").write_text("my library")
            (target / "assets").mkdir()
            (target / "assets/cover.jpg").write_bytes(b"cover")
            (target / "Orbit.exe").write_bytes(b"old app")

            worker = InstallWorker(source, target, desktop=False, start_menu=False)
            worker.run()

            self.assertEqual((target / "Orbit.exe").read_bytes(), b"new app")
            self.assertEqual((target / "data/settings.json").read_text(), "my library")
            self.assertEqual((target / "assets/cover.jpg").read_bytes(), b"cover")

    def test_splash_is_generated_at_expected_size(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            output = Path(temporary) / "splash.png"
            create_splash(output)
            from PIL import Image
            with Image.open(output) as image:
                self.assertEqual(image.size, (560, 300))


if __name__ == "__main__":
    unittest.main()

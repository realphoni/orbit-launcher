import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launcher

class ScannerTests(unittest.TestCase):
    def test_nested_vdf_and_escaped_paths(self):
        with tempfile.TemporaryDirectory(dir=launcher.BASE) as d:
            p = Path(d) / 'test.vdf'
            p.write_text('"libraryfolders" { "0" { "path" "G:\\\\SteamLibrary" "apps" { "620" "123" } } }')
            self.assertEqual(launcher.read_vdf(p)['libraryfolders']['0']['path'], 'G:\\SteamLibrary')

    def test_copy_does_not_change_original(self):
        with tempfile.TemporaryDirectory(dir=launcher.BASE) as d:
            root = Path(d)
            source = root / 'steam/appcache/librarycache/620/hash/library_hero.jpg'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'original artwork')
            assets = root / 'assets'
            assets.mkdir()
            with patch.object(launcher, 'STEAM', root / 'steam'), patch.object(launcher, 'ASSETS', assets):
                result = launcher.artwork('620')
            self.assertIn('hero', result)
            self.assertEqual(source.read_bytes(), (assets / '620_hero.jpg').read_bytes())

    def test_live_scan_has_real_paths_and_unique_ids(self):
        data = launcher.scan()
        ids = [g['id'] for g in data['games']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(Path(g['path']).exists() for g in data['games'] if g['source'] != 'Local'))
        self.assertTrue(all(d['free'] <= d['total'] for d in data['drives']))

if __name__ == '__main__': unittest.main()

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from game_info import validate_profile, fetch_reviews
from library_tools import merge_backup, personal_settings

BASE = Path(__file__).resolve().parent
HOME = Path(sys.executable).parent if getattr(sys, 'frozen', False) else BASE
DATA = HOME / 'data'
ASSETS = HOME / 'assets'
STEAM = Path(r'C:\Program Files (x86)\Steam')

def log_exception(kind, value, tb):
    import traceback
    DATA.mkdir(exist_ok=True)
    (DATA / 'error.log').write_text(''.join(traceback.format_exception(kind, value, tb)), encoding='utf-8')
sys.excepthook = log_exception

def read_vdf(path):
    tokens = re.findall(r'"((?:\\.|[^"\\])*)"|([{}])', Path(path).read_text(encoding='utf-8', errors='replace'))
    items = iter([b if b else a.replace('\\\\', '\\').replace('\\"', '"') for a, b in tokens])
    def obj():
        result = {}
        for key in items:
            if key == '}': break
            value = next(items, '')
            result[key] = obj() if value == '{' else value
        return result
    return obj()

def load_settings():
    try: return json.loads((DATA / 'settings.json').read_text())
    except (OSError, ValueError): return {'favorites': [], 'custom': [], 'played': {}}

def save_settings(value):
    DATA.mkdir(exist_ok=True)
    tmp = DATA / 'settings.tmp'
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(DATA / 'settings.json')

def drive_roots():
    if os.name != 'nt': return []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(f'{chr(65+i)}:/') for i in range(26) if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(f'{chr(65+i)}:\\') in (2, 3)]

def artwork(appid):
    root = STEAM / 'appcache' / 'librarycache'
    folder = root / str(appid)
    result = {}
    for kind, name in [('cover', 'library_600x900'), ('hero', 'library_hero')]:
        candidates = list(folder.rglob(name + '.*')) if folder.exists() else []
        candidates += list(root.glob(f'{appid}_{name}.*'))
        source = next((p for p in candidates if p.suffix.lower() in ('.jpg', '.png', '.webp')), None)
        if source:
            dest = ASSETS / f'{appid}_{kind}{source.suffix}'
            if not dest.exists() or dest.stat().st_size != source.stat().st_size: shutil.copy2(source, dest)
            result[kind] = dest.as_uri()
    return result

def scan():
    ASSETS.mkdir(exist_ok=True)
    roots = drive_roots()
    libraries = {STEAM}
    warnings = []
    try:
        for entry in read_vdf(STEAM / 'steamapps/libraryfolders.vdf').get('libraryfolders', {}).values():
            if isinstance(entry, dict) and entry.get('path'): libraries.add(Path(entry['path']))
    except OSError as e: warnings.append(str(e))
    for root in roots:
        for relative in ['SteamLibrary', 'Steam', 'Games/Steam', 'Program Files (x86)/Steam']:
            p = root / relative
            if (p / 'steamapps').is_dir(): libraries.add(p)
    games = {}
    for library in sorted(libraries):
        try:
            for manifest in (library / 'steamapps').glob('appmanifest_*.acf'):
                try:
                    info = read_vdf(manifest)['AppState']
                    appid = info['appid']
                    path = library / 'steamapps/common' / info['installdir']
                    if not path.is_dir() or appid == '228980': continue
                    game = dict(id='steam:' + appid, appid=appid, name=info['name'], source='Steam', path=str(path), drive=path.drive, size=int(info.get('SizeOnDisk', 0)), updated=int(info.get('LastUpdated', 0)), ready=bool(int(info.get('StateFlags', 0)) & 4))
                    game.update(artwork(appid))
                    games[game['id']] = game
                except (OSError, KeyError, ValueError) as e: warnings.append(f'{manifest.name}: {e}')
        except OSError as e: warnings.append(str(e))
    epic = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Epic/EpicGamesLauncher/Data/Manifests'
    for manifest in epic.glob('*.item'):
        try:
            info = json.loads(manifest.read_text(encoding='utf-8-sig'))
            path = Path(info['InstallLocation'])
            if not path.is_dir() or info.get('bIsIncompleteInstall'): continue
            key = 'epic:' + info['AppName']
            games[key] = dict(id=key, name=info['DisplayName'], source='Epic', path=str(path), drive=path.drive, size=int(info.get('InstallSize', 0)), updated=0, ready=True, appid=info['AppName'])
        except (OSError, ValueError, KeyError) as e: warnings.append(f'{manifest.name}: {e}')
    # Use the most recently changed local Steam profile; do not combine accounts.
    profiles = list((STEAM / 'userdata').glob('*/config/localconfig.vdf'))
    activity = {}
    if profiles:
        try:
            profile = max(profiles, key=lambda p: p.stat().st_mtime)
            node = read_vdf(profile)
            for key in ('userlocalconfigstore', 'software', 'valve', 'steam', 'apps'):
                node = next((v for k, v in node.items() if k.lower() == key), {})
            activity = node
        except (OSError, ValueError, AttributeError): pass
    for game in games.values():
        entry = activity.get(game.get('appid'), {}) if game['source'] == 'Steam' else {}
        try:
            if 'Playtime' in entry: game['minutes'] = int(entry['Playtime'])
            game['lastPlayed'] = int(entry.get('LastPlayed', 0))
        except (ValueError, TypeError): pass
    settings = load_settings()
    for game in settings.get('custom', []):
        game['ready'] = Path(game['path']).is_file()
        games[game['id']] = game
    drives = []
    for root in roots:
        try:
            usage = shutil.disk_usage(root)
            drives.append(dict(name=root.drive, total=usage.total, free=usage.free))
        except OSError: pass
    try: reviews = json.loads((DATA / 'reviews.json').read_text())
    except (OSError, ValueError): reviews = {}
    return dict(games=sorted(games.values(), key=lambda g: g['name'].casefold()), drives=drives, warnings=warnings, scanned=int(time.time()), settings=settings, reviews=reviews)

def main():
    from PySide6.QtCore import QObject, Signal, Slot, QThread, QUrl, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtGui import QShortcut, QKeySequence, QIcon

    class Worker(QThread):
        done = Signal(str)
        def run(self):
            try: self.done.emit(json.dumps(scan()))
            except Exception as e: self.done.emit(json.dumps({'error': str(e)}))

    class ReviewWorker(QThread):
        done = Signal(str)
        def __init__(self, key, appid):
            super().__init__()
            self.key, self.appid = key, appid
        def run(self):
            try: self.done.emit(json.dumps(dict(id=self.key, review=fetch_reviews(self.appid))))
            except Exception as e: self.done.emit(json.dumps(dict(id=self.key, error='Could not load Steam reviews. Check your connection and try again.')))

    class Bridge(QObject):
        library = Signal(str)
        notice = Signal(str)
        settingsChanged = Signal(str)
        reviewReady = Signal(str)
        def __init__(self):
            super().__init__()
            self.games = {}
            self.worker = None
            self.review_workers = []
        @Slot(str, str)
        def libraryAction(self, key, action):
            if key not in self.games: return
            settings = load_settings()
            if action in ('queue', 'hide'):
                field = 'queue' if action == 'queue' else 'hidden'
                values = settings.setdefault(field, [])
                if key in values: values.remove(key)
                else: values.append(key)
            elif action == 'first':
                settings['queue'] = [key] + [v for v in settings.get('queue', []) if v != key]
            else: return
            try:
                save_settings(settings)
                self.settingsChanged.emit(json.dumps(settings))
            except OSError as e: self.notice.emit(str(e))
        @Slot(str)
        def coverSize(self, value):
            if value not in ('small','medium','large'): return
            try:
                settings = load_settings()
                settings['coverSize'] = value
                save_settings(settings)
                self.settingsChanged.emit(json.dumps(settings))
            except OSError as e: self.notice.emit(str(e))
        @Slot()
        def exportBackup(self):
            path, _ = QFileDialog.getSaveFileName(view, 'Export personal library', 'Orbit-library-backup.json', 'Orbit backup (*.json)')
            if not path: return
            try:
                document = dict(format='orbit-personal-library',version=1,settings=personal_settings(load_settings()))
                Path(path).write_text(json.dumps(document, indent=2), encoding='utf-8')
                self.notice.emit('Personal library exported')
            except OSError as e: self.notice.emit(str(e))
        @Slot()
        def importBackup(self):
            path, _ = QFileDialog.getOpenFileName(view, 'Restore personal library', '', 'Orbit backup (*.json)')
            if not path: return
            try:
                if Path(path).stat().st_size > 10_000_000: raise ValueError('Backup is too large')
                current = load_settings()
                restored = merge_backup(current, json.loads(Path(path).read_text(encoding='utf-8-sig')))
                (DATA / 'settings-before-restore.json').write_text(json.dumps(current,indent=2))
                save_settings(restored)
                self.settingsChanged.emit(json.dumps(restored))
                self.notice.emit('Backup merged. Previous settings saved in data/settings-before-restore.json')
            except (OSError, ValueError) as e: self.notice.emit(str(e))
        @Slot(str, str)
        def saveProfile(self, key, raw):
            if key not in self.games: return
            try:
                profile = validate_profile(json.loads(raw))
                settings = load_settings()
                settings.setdefault('profiles', {})[key] = profile
                save_settings(settings)
                self.settingsChanged.emit(json.dumps(settings))
                self.notice.emit('Game details saved')
            except (OSError, ValueError) as e: self.notice.emit(str(e))
        @Slot(str)
        def reviews(self, key):
            game = self.games.get(key)
            if not game or game['source'] != 'Steam': return
            if any(w.key == key and w.isRunning() for w in self.review_workers): return
            if sum(w.isRunning() for w in self.review_workers) >= 3:
                self.reviewReady.emit(json.dumps(dict(id=key, error='Please wait for the other review requests to finish.')))
                return
            worker = ReviewWorker(key, game['appid'])
            self.review_workers.append(worker)
            worker.done.connect(self.reviewFinished)
            worker.start()
        @Slot(str)
        def reviewFinished(self, raw):
            result = json.loads(raw)
            if 'review' in result:
                try:
                    try: cache = json.loads((DATA / 'reviews.json').read_text())
                    except (OSError, ValueError): cache = {}
                    cache[result['id']] = result['review']
                    (DATA / 'reviews.json').write_text(json.dumps(cache))
                except OSError: self.notice.emit('Reviews loaded, but could not save the offline cache.')
            self.reviewReady.emit(raw)
        @Slot(str)
        def storePage(self, key):
            game = self.games.get(key)
            if game and game['source'] == 'Steam' and game['appid'].isdigit():
                os.startfile('https://store.steampowered.com/app/' + game['appid'] + '/')
        @Slot()
        def refresh(self):
            with (DATA / 'startup.log').open('a') as log: log.write('refresh called\n')
            if self.worker and self.worker.isRunning(): return
            self.worker = Worker()
            self.worker.done.connect(self.finished)
            self.worker.start()
        @Slot(str)
        def finished(self, result):
            with (DATA / 'startup.log').open('a') as log: log.write('scan completed\n')
            data = json.loads(result)
            if 'games' in data:
                self.games = {g['id']: g for g in data['games']}
                data['settings'] = load_settings()
                result = json.dumps(data)
            self.library.emit(result)
        @Slot(str)
        def launch(self, key):
            game = self.games.get(key)
            if not game: return
            try:
                if not game['ready']: raise RuntimeError('Game is unavailable or needs an update in its client.')
                if game['source'] == 'Steam':
                    subprocess.Popen([str(STEAM / 'steam.exe'), '-applaunch', game['appid']])
                elif game['source'] == 'Epic':
                    from urllib.parse import quote
                    os.startfile('com.epicgames.launcher://apps/' + quote(game['appid'], safe='') + '?action=launch&silent=true')
                else: subprocess.Popen([game['path']], cwd=str(Path(game['path']).parent))
                settings = load_settings()
                settings.setdefault('played', {})[key] = int(time.time())
                save_settings(settings)
                self.settingsChanged.emit(json.dumps(settings))
                self.notice.emit('Launch requested: ' + game['name'])
                view.showMinimized()
            except Exception as e: self.notice.emit(str(e))
        @Slot(str)
        def favorite(self, key):
            settings = load_settings()
            favorites = settings.setdefault('favorites', [])
            if key in favorites: favorites.remove(key)
            else: favorites.append(key)
            save_settings(settings)
        @Slot(str)
        def theme(self, name):
            if name not in ('orbit', 'ocean', 'violet', 'ember'): return
            settings = load_settings()
            settings['theme'] = name
            save_settings(settings)
        @Slot(str)
        def folder(self, key):
            if key in self.games:
                path = Path(self.games[key]['path'])
                try: os.startfile(str(path if path.is_dir() else path.parent))
                except OSError as e: self.notice.emit(str(e))
        @Slot()
        def add(self):
            path, _ = QFileDialog.getOpenFileName(view, 'Add a game', '', 'Windows executable (*.exe)')
            if not path: return
            p = Path(path)
            game = dict(id='custom:' + hashlib.sha256(str(p).lower().encode()).hexdigest()[:16], name=p.stem, source='Local', path=str(p), drive=p.drive, size=p.stat().st_size, updated=0, ready=True)
            settings = load_settings()
            settings['custom'] = [g for g in settings.get('custom', []) if g['id'] != game['id']] + [game]
            save_settings(settings)
            self.refresh()
        @Slot()
        def fullscreen(self):
            view.showNormal() if view.isFullScreen() else view.showFullScreen()
        @Slot()
        def quit(self):
            if self.worker and self.worker.isRunning():
                self.notice.emit('Finishing library scan. Please exit again in a moment.')
                return
            app.quit()

    app = QApplication(sys.argv)
    DATA.mkdir(exist_ok=True)
    class Page(QWebEnginePage):
        def javaScriptConsoleMessage(self, level, message, line, source):
            with (DATA / 'startup.log').open('a', encoding='utf-8') as log:
                log.write(f'JS {line}: {message}\n')
    app.setApplicationName('Orbit • Game Launcher')
    app.setWindowIcon(QIcon(str(BASE / 'orbit.ico')))
    view = QWebEngineView()
    view.setPage(Page(view))
    view.setWindowTitle('Orbit • Game Launcher')
    view.resize(1440, 900)
    bridge = Bridge()
    channel = QWebChannel()
    channel.registerObject('launcher', bridge)
    view.page().setWebChannel(channel)
    view.load(QUrl.fromLocalFile(str(BASE / 'index.html')))
    shortcut = QShortcut(QKeySequence('F11'), view)
    shortcut.activated.connect(bridge.fullscreen)
    def wait_workers():
        if bridge.worker and bridge.worker.isRunning(): bridge.worker.wait()
        for worker in bridge.review_workers: worker.wait()
    app.aboutToQuit.connect(wait_workers)
    if '--windowed' in sys.argv: view.show()
    else: view.showFullScreen()
    if '--smoke-test' in sys.argv:
        def inspect():
            view.page().runJavaScript("JSON.stringify({cards:document.querySelectorAll('.card').length,status:document.getElementById('status').textContent,channel:typeof QWebChannel,qt:typeof qt})", report)
        def report(value):
            (DATA / 'smoke-test.json').write_text(value or '{}')
            app.exit(0 if json.loads(value or '{}').get('cards', 0) > 0 else 1)
        QTimer.singleShot(12000, inspect)
    sys.exit(app.exec())

if __name__ == '__main__':
    if '--scan' in sys.argv:
        result = scan()
        DATA.mkdir(exist_ok=True)
        (DATA / 'library.json').write_text(json.dumps(result, indent=2))
        print(f"Found {len(result['games'])} games across {len(result['drives'])} drives; {len(result['warnings'])} warnings")
    else: main()

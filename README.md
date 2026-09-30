# O R B I T™ Launcher

A fullscreen Windows game launcher with a local library and copied Steam artwork.

This repository contains the launcher source. Personal library data, Steam artwork, and generated Windows binaries are excluded.

On Windows with Python 3.10 or newer, install dependencies with `python -m pip install -r requirements.txt`. Start fullscreen with **Start Orbit.bat** or `python launcher.py`; use `python launcher.py --windowed` for a normal window.

To build a standalone Windows app, run `python -m pip install -r requirements-build.txt`, then `python build.py`. Open **release/Orbit/Orbit.exe**. The built app does not require Python to be installed. Keep the entire `release/Orbit` folder together: `_internal` contains its runtime. Settings and copied artwork are saved alongside the executable, so use a writable folder. Existing local installations may live at **dist/Orbit/Orbit.exe**.

## Installer

After building the portable app, run `python build_installer.py`. The result is **release/installer/OrbitSetup.exe**, a single-file native Windows installer. Its animated setup screen lets users choose an install folder and optional Desktop and Start-menu shortcuts. The default location is `%LOCALAPPDATA%\Programs\Orbit`, so Orbit can save its local library without administrator rights.

Installing over an existing copy is a safe upgrade: the installer stages the new build first, carries forward `data` and `assets`, and restores the previous installation if activation fails. Close Orbit before upgrading so Windows does not lock application files. The installer payload deliberately excludes the developer's personal library and copied Steam artwork.

Builds are staged under `release/Orbit`, so building never deletes the live app's settings or artwork. After testing, close Orbit and copy the staged executable and `_internal` contents into `dist/Orbit`, preserving `data` and `assets`.

## Game details and library organization

Orbit opens on **Home**, with recent Steam/Orbit activity, favorites, library totals, and your **Play next** queue. Add or remove games from the queue in game details; Home lets you move queued games to the front or remove them. Hidden and disconnected games stay out of Home without losing their queue entries.

Use **Hide game** in details to declutter the library. The **Hidden** tab lets you find and unhide games. Hiding never uninstalls or deletes a game. **Reset filters** clears searches and filters without changing the selected tab.

Settings includes small, medium, and large library covers. **Export backup** saves personal ratings, notes, collections, favorites, queue, hidden games, and appearance to JSON. **Restore backup** merges lists and replaces matching game profiles; it preserves launch paths and history, and saves the prior settings to `data/settings-before-restore.json`. Game files, executable paths, Steam reviews, and artwork are not included in these personal-library backups.

Open a game to give it a personal 1–5 star rating, record notes, assign comma-separated collections, or mark it Want to play, Playing, Completed, On hold, or Dropped. Click **Save game details** to persist edits. Personal scores stay on your PC.

Steam games show locally cached playtime and last-played dates from the most recently modified local Steam profile. These may lag Steam until refreshed; multiple accounts are not combined. Recent activity also includes Orbit's recorded launch requests, which do not guarantee a successful game start.

**Load Steam rating** requests real public review totals, positive percentage, and sentiment using [Valve's documented review API](https://partner.steamgames.com/doc/store/getreviews). Reviews use all languages and purchase types, with Steam's default off-topic filtering. Results show a fetch date and are cached for offline viewing. Failed requests retain previous cached scores. Epic and manually added games support personal ratings only.

Filter by collection, play status, or drive; sort by personal rating or Steam playtime. **Surprise me** opens details for an available game from the current filtered view without launching it. The summary counts rated/completed games and available Steam hours.

Open **Settings → Scan games** to refresh connected game libraries. The button shows scan progress and the result. Settings also offers four saved color themes: Orbit green, Ocean blue, Violet dusk, and Warm ember.

- Reads Steam library registrations and installed app manifests across drives, plus common Steam library paths on fixed/removable drives.
- Reads Epic installation manifests. Add other games using **Add game** and select their executable. It does not indiscriminately treat every executable on a drive as a game.
- Copies cached game covers and hero images from `C:\Program Files (x86)\Steam\appcache\librarycache` into `assets`. Original Steam files are never modified or moved. Missing artwork gets a title card. These third-party assets retain their original rights; they are not bundled for public redistribution.
- Shows actual installation size from manifests and disk capacity. Manually added games show executable size, explicitly labeled in details.
- Favorites and Orbit launch history live in `data/settings.json`. Recently launched means launched through Orbit.
- Steam/Epic games launch through their respective clients; local games launch their selected executable. Orbit minimizes after submitting a launch request. Restore it from the taskbar.
- Keyboard arrows navigate; Enter opens details/activates controls; Escape closes dialogs or returns to Library; F11 toggles fullscreen. Standard browser-compatible gamepads use D-pad/left stick, A and B.

Scanning runs in a background thread. Offline drives are skipped. Refresh after reconnecting a drive. Community ratings are fetched on request; scanning and personal metadata work offline. Gamepad mappings depend on the controller and Qt's browser support.

For a scan report without opening a window: `python launcher.py --scan`.

The startup bridge delivers background scan results through a Qt slot on the UI thread. To verify the real desktop startup (rather than injecting fixture data), run `Orbit.exe --windowed --smoke-test`. It closes after 12 seconds and writes `data/smoke-test.json`; a successful run has a nonzero `cards` count and exit code 0. JavaScript diagnostics are recorded in `data/startup.log`.

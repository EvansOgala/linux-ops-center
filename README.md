# Linux Ops Center

A Python desktop app with three operations-focused tabs:

- Systemd Dashboard: list/filter services, start/stop/restart/enable/disable, view logs.
- Disk Usage Visualizer: top-level folder usage + largest files scanner.
- Package Audit Tool: update/orphan/cache hints for pacman/apt/dnf/flatpak and one-click terminal actions.

## Run

```bash
cd /home/'your username'/Documents/linux-ops-center
python3 main.py
```

## Build AppImage

```bash
cd /home/evans/Documents/linux-ops-center
python3 -m pip install --user pyinstaller
# place appimagetool at ./tools/appimagetool.AppImage (or install appimagetool in PATH)
./build-appimage.sh
```

# Linux Ops Center

GTK4 operations dashboard for service control, disk auditing, and package maintenance hints.

## Features

- Systemd service browser with start/stop/restart/enable/disable actions
- Service log viewer
- Disk usage scan and largest-files view
- Package audit helpers for `pacman`, `apt`, `dnf`, and `flatpak`
- One-click command launch in an available terminal emulator

## Dependencies

### Runtime

- Python 3.11+
- GTK4 + PyGObject
- `systemd` tools (`systemctl`, `journalctl`) for service features
- At least one supported terminal emulator (`x-terminal-emulator`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `kitty`, `alacritty`, or `xterm`)
- Optional: `pkexec` for privileged service operations

### Install dependencies by distro

#### Arch Linux / Nyarch

```bash
sudo pacman -S --needed python python-gobject gtk4 systemd xdg-utils polkit
```

#### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-gi gir1.2-gtk-4.0 systemd xdg-utils policykit-1 xterm
```

#### Fedora

```bash
sudo dnf install -y python3 python3-gobject gtk4 systemd xdg-utils polkit xterm
```

## Run from source

```bash
cd /home/'your username'/Documents/linux-ops-center
python3 main.py
```

## Build AppImage

### Build requirements

```bash
python3 -m pip install --user pyinstaller
```

Install `appimagetool` in `PATH`, or place one of these files in `./tools/`:

- `appimagetool.AppImage`
- `appimagetool-x86_64.AppImage`

### Build command

```bash
cd /home/'your username'/Documents/linux-ops-center
chmod +x build-appimage.sh
./build-appimage.sh
```

The script outputs an `.AppImage` file in the project root.

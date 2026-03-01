import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuditResult:
    manager: str
    summary: str
    details: str


def _run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        c = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)
    out = (c.stdout or "") + (c.stderr or "")
    return c.returncode, out.strip()


def detect_managers() -> list[str]:
    out = []
    for name in ("pacman", "apt", "dnf", "flatpak"):
        if shutil.which(name):
            out.append(name)
    return out


def _audit_pacman() -> AuditResult:
    cmd_updates = ["checkupdates"] if shutil.which("checkupdates") else ["pacman", "-Qu"]
    _, update_out = _run(cmd_updates)
    updates = [l for l in update_out.splitlines() if l.strip()]

    _, orphan_out = _run(["pacman", "-Qdtq"])
    orphans = [l for l in orphan_out.splitlines() if l.strip()]

    _, cache_out = _run(["du", "-sh", "/var/cache/pacman/pkg"])
    cache_size = cache_out.split()[0] if cache_out else "unknown"

    summary = f"updates={len(updates)} | orphans={len(orphans)} | cache={cache_size}"
    details = []
    details.append("Update command: " + " ".join(cmd_updates))
    details.append("Orphan command: pacman -Qdtq")
    details.append("System upgrade: sudo pacman -Syu")
    details.append("Orphan cleanup: sudo pacman -Rns $(pacman -Qdtq)")
    details.append("Cache cleanup: sudo paccache -r")
    if updates:
        details.append("\nUpgradable packages:\n" + "\n".join(updates[:200]))
    if orphans:
        details.append("\nOrphan packages:\n" + "\n".join(orphans[:200]))
    return AuditResult("pacman", summary, "\n".join(details))


def _audit_apt() -> AuditResult:
    _, update_out = _run(["apt", "list", "--upgradable"])
    updates = [l for l in update_out.splitlines() if l.strip() and not l.startswith("Listing")]

    _, auto_out = _run(["apt", "autoremove", "--dry-run"])
    removable = [l for l in auto_out.splitlines() if "Remv" in l or "remove" in l.lower()]

    summary = f"updates={len(updates)} | autoremove candidates={len(removable)}"
    details = []
    details.append("Update command: apt list --upgradable")
    details.append("System upgrade: sudo apt update && sudo apt upgrade")
    details.append("Cleanup: sudo apt autoremove && sudo apt clean")
    if updates:
        details.append("\nUpgradable packages:\n" + "\n".join(updates[:200]))
    if removable:
        details.append("\nAutoremove candidates:\n" + "\n".join(removable[:200]))
    return AuditResult("apt", summary, "\n".join(details))


def _audit_dnf() -> AuditResult:
    _, check_out = _run(["dnf", "check-update"])
    lines = [l for l in check_out.splitlines() if l.strip()]

    summary = f"check-output-lines={len(lines)}"
    details = []
    details.append("Check command: dnf check-update")
    details.append("System upgrade: sudo dnf upgrade --refresh")
    details.append("Autoremove: sudo dnf autoremove")
    if lines:
        details.append("\nCheck output:\n" + "\n".join(lines[:250]))
    return AuditResult("dnf", summary, "\n".join(details))


def _audit_flatpak() -> AuditResult:
    _, update_out = _run(["flatpak", "remote-ls", "--updates"])
    updates = [l for l in update_out.splitlines() if l.strip()]

    _, unused_out = _run(["flatpak", "uninstall", "--unused", "--assumeno"])
    unused = [l for l in unused_out.splitlines() if l.strip()]

    summary = f"updates={len(updates)} | unused-hints={len(unused)}"
    details = []
    details.append("Update command: flatpak remote-ls --updates")
    details.append("System upgrade: flatpak update")
    details.append("Cleanup: flatpak uninstall --unused")
    if updates:
        details.append("\nUpgradable refs:\n" + "\n".join(updates[:200]))
    if unused:
        details.append("\nUnused refs hint:\n" + "\n".join(unused[:200]))
    return AuditResult("flatpak", summary, "\n".join(details))


def audit_all() -> list[AuditResult]:
    results: list[AuditResult] = []
    managers = detect_managers()
    for m in managers:
        if m == "pacman":
            results.append(_audit_pacman())
        elif m == "apt":
            results.append(_audit_apt())
        elif m == "dnf":
            results.append(_audit_dnf())
        elif m == "flatpak":
            results.append(_audit_flatpak())
    return results


def launch_in_terminal(command: str, title: str = "Linux Ops Center") -> tuple[bool, str]:
    shell_cmd = (
        f"echo '[{title}]'; echo; {command}; rc=$?; echo; "
        "if [ $rc -eq 0 ]; then echo Done.; else echo Failed with exit code $rc.; fi; "
        "echo; read -r -p 'Press Enter to close...' _"
    )

    terminals = [
        ["x-terminal-emulator", "-e", "bash", "-lc", shell_cmd],
        ["gnome-terminal", "--", "bash", "-lc", shell_cmd],
        ["konsole", "-e", "bash", "-lc", shell_cmd],
        ["xfce4-terminal", "-x", "bash", "-lc", shell_cmd],
        ["kitty", "bash", "-lc", shell_cmd],
        ["alacritty", "-e", "bash", "-lc", shell_cmd],
        ["xterm", "-e", "bash", "-lc", shell_cmd],
    ]

    in_flatpak = Path("/.flatpak-info").exists()
    spawn = shutil.which("flatpak-spawn")

    for cmd in terminals:
        bin_name = cmd[0]
        try:
            if in_flatpak and spawn:
                subprocess.Popen(["flatpak-spawn", "--host", *cmd])
                return True, f"Launched in host terminal: {command}"
            if shutil.which(bin_name) is None:
                continue
            subprocess.Popen(cmd)
            return True, f"Launched in terminal: {command}"
        except Exception:  # noqa: BLE001
            continue

    if in_flatpak and not spawn:
        return False, "flatpak-spawn is missing in this sandbox."
    return False, "No supported terminal emulator found."


def recommended_system_upgrade(managers: list[str]) -> str:
    if "pacman" in managers:
        return "sudo pacman -Syu"
    if "apt" in managers:
        return "sudo apt update && sudo apt upgrade"
    if "dnf" in managers:
        return "sudo dnf upgrade --refresh"
    return ""


def recommended_cleanup(managers: list[str]) -> str:
    if "pacman" in managers:
        return "sudo paccache -r"
    if "apt" in managers:
        return "sudo apt autoremove && sudo apt clean"
    if "dnf" in managers:
        return "sudo dnf autoremove"
    return ""

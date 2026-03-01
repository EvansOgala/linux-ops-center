import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class ServiceRow:
    unit: str
    load: str
    active: str
    sub: str
    description: str


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)
    out = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, out.strip()


def has_systemd() -> bool:
    return shutil.which("systemctl") is not None


def list_services(search: str = "", state_filter: str = "all", limit: int = 700) -> list[ServiceRow]:
    if not has_systemd():
        return []

    code, out = _run(["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"], timeout=90)
    if code != 0:
        return []

    rows: list[ServiceRow] = []
    search_text = search.strip().lower()

    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 4)
        if len(parts) < 5:
            continue

        row = ServiceRow(
            unit=parts[0],
            load=parts[1],
            active=parts[2],
            sub=parts[3],
            description=parts[4],
        )

        if state_filter == "running" and row.active != "active":
            continue
        if state_filter == "failed" and row.active != "failed":
            continue
        if state_filter == "inactive" and row.active not in {"inactive", "dead"}:
            continue

        if search_text:
            hay = f"{row.unit} {row.description}".lower()
            if search_text not in hay:
                continue

        rows.append(row)
        if len(rows) >= limit:
            break

    rows.sort(key=lambda r: (r.active != "failed", r.active != "active", r.unit))
    return rows


def _privileged_systemctl_cmd(action: str, unit: str) -> list[str]:
    if os.geteuid() == 0:
        return ["systemctl", action, unit]
    if shutil.which("pkexec"):
        return ["pkexec", "systemctl", action, unit]
    return ["systemctl", action, unit]


def run_service_action(action: str, unit: str) -> tuple[bool, str]:
    allowed = {"start", "stop", "restart", "enable", "disable"}
    if action not in allowed:
        return False, f"Unsupported action: {action}"
    if not has_systemd():
        return False, "systemctl is not available on this machine."

    cmd = _privileged_systemctl_cmd(action, unit)
    code, out = _run(cmd, timeout=120)
    if code == 0:
        return True, f"{action.title()} succeeded for {unit}."

    details = out or "No output."
    if cmd[0] == "systemctl":
        details += "\n\nTip: install/use pkexec, or run app as root for privileged actions."
    return False, details


def read_service_logs(unit: str, lines: int = 120) -> str:
    if not has_systemd():
        return "systemctl/journalctl is not available."

    lines = max(20, min(1000, int(lines)))
    code, out = _run(
        ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "-o", "short-iso"],
        timeout=90,
    )
    if code == 0 and out:
        return out

    code2, out2 = _run(["systemctl", "status", unit, "--no-pager"], timeout=60)
    if code2 == 0 and out2:
        return out2
    return out or out2 or "No logs available."

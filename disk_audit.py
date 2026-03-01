import heapq
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiskItem:
    path: Path
    size: int
    item_type: str


def human_size(num: int) -> str:
    size = float(max(0, num))
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} EB"


def _is_hidden(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts if part not in {".", ".."})


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _dir_size(path: Path, root: Path, show_hidden: bool) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=True, onerror=lambda _e: None):
        base = Path(dirpath)
        if not show_hidden:
            dirnames[:] = [d for d in dirnames if not _is_hidden(base / d, root)]
        for name in filenames:
            fp = base / name
            if not show_hidden and _is_hidden(fp, root):
                continue
            total += _safe_file_size(fp)
    return total


def summarize_top_level(root: Path, show_hidden: bool = False) -> list[DiskItem]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Path is not a directory: {root}")

    items: list[DiskItem] = []
    for entry in root.iterdir():
        if not show_hidden and entry.name.startswith("."):
            continue
        if entry.is_symlink():
            continue

        if entry.is_dir():
            size = _dir_size(entry, root, show_hidden)
            item_type = "dir"
        else:
            size = _safe_file_size(entry)
            item_type = "file"

        items.append(DiskItem(path=entry, size=size, item_type=item_type))

    items.sort(key=lambda i: i.size, reverse=True)
    return items


def largest_files(root: Path, show_hidden: bool = False, limit: int = 120) -> list[DiskItem]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Path is not a directory: {root}")

    limit = max(10, min(1000, int(limit)))
    heap: list[tuple[int, str]] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=lambda _e: None):
        base = Path(dirpath)
        if not show_hidden:
            dirnames[:] = [d for d in dirnames if not _is_hidden(base / d, root)]
        for name in filenames:
            path = base / name
            if not show_hidden and _is_hidden(path, root):
                continue

            size = _safe_file_size(path)
            key = str(path)
            if len(heap) < limit:
                heapq.heappush(heap, (size, key))
            elif size > heap[0][0]:
                heapq.heapreplace(heap, (size, key))

    out = [DiskItem(path=Path(p), size=s, item_type="file") for s, p in heap]
    out.sort(key=lambda i: i.size, reverse=True)
    return out


def scan_disk(path: str, show_hidden: bool = False) -> tuple[list[DiskItem], list[DiskItem], Path]:
    root = Path(path).expanduser().resolve()
    top = summarize_top_level(root, show_hidden=show_hidden)
    files = largest_files(root, show_hidden=show_hidden, limit=150)
    return top, files, root

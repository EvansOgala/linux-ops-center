import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from disk_audit import human_size, scan_disk
from package_audit import (
    audit_all,
    detect_managers,
    launch_in_terminal,
    recommended_cleanup,
    recommended_system_upgrade,
)
from service_ops import has_systemd, list_services, read_service_logs, run_service_action
from settings import load_settings, save_settings

THEMES = {
    "dark": {
        "root": "#0f172a",
        "panel": "#111827",
        "card": "#0b1220",
        "line": "#1f2937",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "entry": "#020617",
        "entry_fg": "#dbeafe",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_press": "#1d4ed8",
        "accent_text": "#eff6ff",
        "select": "#2563eb",
        "warn": "#f87171",
    },
    "light": {
        "root": "#f1f5f9",
        "panel": "#ffffff",
        "card": "#f8fafc",
        "line": "#dbe3ee",
        "text": "#0f172a",
        "muted": "#475569",
        "entry": "#ffffff",
        "entry_fg": "#0f172a",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_press": "#1d4ed8",
        "accent_text": "#eff6ff",
        "select": "#93c5fd",
        "warn": "#dc2626",
    },
}


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=118, height=34, radius=14):
        super().__init__(parent, width=width, height=height, bd=0, highlightthickness=0, relief="flat", cursor="hand2")
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.radius = radius
        self.pressed = False
        self.enabled = True
        self.colors = {
            "bg": "#2563eb",
            "hover": "#3b82f6",
            "press": "#1d4ed8",
            "fg": "#eff6ff",
            "container": "#0f172a",
            "disabled": "#475569",
        }
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def configure_theme(self, palette, container_bg):
        self.colors.update(
            {
                "bg": palette["accent"],
                "hover": palette["accent_hover"],
                "press": palette["accent_press"],
                "fg": palette["accent_text"],
                "container": container_bg,
            }
        )
        self._draw()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def _rounded(self, color):
        w, h, r = self.width, self.height, self.radius
        self.create_arc(0, 0, 2 * r, 2 * r, start=90, extent=90, fill=color, outline=color)
        self.create_arc(w - 2 * r, 0, w, 2 * r, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, h - 2 * r, 2 * r, h, start=180, extent=90, fill=color, outline=color)
        self.create_arc(w - 2 * r, h - 2 * r, w, h, start=270, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h - r, fill=color, outline=color)

    def _draw(self):
        self.delete("all")
        self.configure(bg=self.colors["container"])
        color = self.colors["disabled"] if not self.enabled else (self.colors["press"] if self.pressed else self.colors["bg"])
        self._rounded(color)
        self.create_text(self.width // 2, self.height // 2, text=self.text, fill=self.colors["fg"], font=("Adwaita Sans", 10, "bold"))

    def _on_enter(self, _event):
        if self.enabled and not self.pressed:
            self.delete("all")
            self.configure(bg=self.colors["container"])
            self._rounded(self.colors["hover"])
            self.create_text(self.width // 2, self.height // 2, text=self.text, fill=self.colors["fg"], font=("Adwaita Sans", 10, "bold"))

    def _on_leave(self, _event):
        self.pressed = False
        self._draw()

    def _on_press(self, _event):
        if not self.enabled:
            return
        self.pressed = True
        self._draw()

    def _on_release(self, _event):
        if not self.enabled:
            return
        run = self.pressed
        self.pressed = False
        self._draw()
        if run:
            self.command()


class LinuxOpsCenterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Linux Ops Center")
        self.root.geometry("1280x840")
        self.root.minsize(1050, 680)

        self.settings = load_settings()
        self.theme_var = tk.StringVar(value=self.settings.get("theme", "dark"))
        self.service_search_var = tk.StringVar(value=self.settings.get("service_search", ""))
        self.service_state_var = tk.StringVar(value=self.settings.get("service_state_filter", "all"))
        self.scan_path_var = tk.StringVar(value=self.settings.get("scan_path", str(Path.home())))
        self.show_hidden_var = tk.BooleanVar(value=bool(self.settings.get("show_hidden", False)))

        self.managers: list[str] = []
        self.round_buttons: list[RoundedButton] = []

        self._build_ui()
        self.apply_theme(self.theme_var.get())

        self.refresh_services()
        self.scan_disk()
        self.refresh_packages()

    def _add_btn(self, btn: RoundedButton):
        self.round_buttons.append(btn)
        return btn

    def _build_ui(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.header = tk.Frame(self.root, padx=14, pady=12)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.columnconfigure(1, weight=1)

        self.title = tk.Label(self.header, text="Linux Ops Center", font=("Adwaita Sans", 24, "bold"))
        self.title.grid(row=0, column=0, sticky="w")

        self.subtitle = tk.Label(self.header, text="Systemd dashboard, disk usage visualizer, package audit", font=("Adwaita Sans", 10))
        self.subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.theme_box = ttk.Combobox(self.header, textvariable=self.theme_var, values=("dark", "light"), state="readonly", width=10, style="App.TCombobox")
        self.theme_box.grid(row=0, column=2, rowspan=2, sticky="e")
        self.theme_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_theme(self.theme_var.get()))

        self.tabs = ttk.Notebook(self.root)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))

        self._build_services_tab()
        self._build_disk_tab()
        self._build_package_tab()

        self.status_var = tk.StringVar(value="Ready")
        self.status = tk.Label(self.root, textvariable=self.status_var, anchor="w", padx=14, pady=8, font=("Adwaita Sans", 10))
        self.status.grid(row=2, column=0, sticky="ew")

    def _build_services_tab(self):
        tab = tk.Frame(self.tabs)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=3)
        tab.rowconfigure(3, weight=2)
        self.tabs.add(tab, text="Systemd")
        self.tab_systemd = tab

        controls = tk.Frame(tab, padx=12, pady=10)
        controls.grid(row=0, column=0, sticky="ew")

        self.lbl_search = tk.Label(controls, text="Search", font=("Adwaita Sans", 10, "bold"))
        self.lbl_search.pack(side="left")
        self.entry_service_search = tk.Entry(controls, textvariable=self.service_search_var, font=("Adwaita Sans", 10), width=26)
        self.entry_service_search.pack(side="left", padx=(6, 12))
        self.entry_service_search.bind("<Return>", lambda _e: self.refresh_services())

        self.lbl_state = tk.Label(controls, text="State", font=("Adwaita Sans", 10, "bold"))
        self.lbl_state.pack(side="left")
        self.box_service_state = ttk.Combobox(controls, textvariable=self.service_state_var, values=("all", "running", "failed", "inactive"), state="readonly", width=10, style="App.TCombobox")
        self.box_service_state.pack(side="left", padx=(6, 10))
        self.box_service_state.bind("<<ComboboxSelected>>", lambda _e: self.refresh_services())

        self.btn_refresh_services = self._add_btn(RoundedButton(controls, "Refresh", self.refresh_services, width=96))
        self.btn_refresh_services.pack(side="left")

        actions = tk.Frame(tab, padx=12, pady=4)
        actions.grid(row=1, column=0, sticky="ew")

        self.btn_start = self._add_btn(RoundedButton(actions, "Start", lambda: self._do_service_action("start"), width=90))
        self.btn_stop = self._add_btn(RoundedButton(actions, "Stop", lambda: self._do_service_action("stop"), width=90))
        self.btn_restart = self._add_btn(RoundedButton(actions, "Restart", lambda: self._do_service_action("restart"), width=90))
        self.btn_enable = self._add_btn(RoundedButton(actions, "Enable", lambda: self._do_service_action("enable"), width=90))
        self.btn_disable = self._add_btn(RoundedButton(actions, "Disable", lambda: self._do_service_action("disable"), width=90))
        self.btn_logs = self._add_btn(RoundedButton(actions, "Show Logs", self.show_selected_logs, width=108))

        for btn in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_enable, self.btn_disable, self.btn_logs):
            btn.pack(side="left", padx=(0, 8))

        table_frame = tk.Frame(tab, padx=12, pady=6)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.service_tree = ttk.Treeview(
            table_frame,
            columns=("unit", "load", "active", "sub", "description"),
            show="headings",
            style="App.Treeview",
        )
        for col, text, width in (
            ("unit", "Service", 250),
            ("load", "Load", 90),
            ("active", "Active", 90),
            ("sub", "Sub", 130),
            ("description", "Description", 500),
        ):
            self.service_tree.heading(col, text=text)
            self.service_tree.column(col, width=width, anchor="w")
        self.service_tree.grid(row=0, column=0, sticky="nsew")
        self.service_tree.bind("<Double-1>", lambda _e: self.show_selected_logs())

        s1 = ttk.Scrollbar(table_frame, orient="vertical", command=self.service_tree.yview)
        self.service_tree.configure(yscrollcommand=s1.set)
        s1.grid(row=0, column=1, sticky="ns")

        logs_frame = tk.LabelFrame(tab, text="Service Logs", padx=10, pady=8)
        logs_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 8))
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        self.logs_frame = logs_frame

        self.logs_text = tk.Text(logs_frame, wrap="word", font=("Adwaita Mono", 10), state="disabled")
        self.logs_text.grid(row=0, column=0, sticky="nsew")
        s2 = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=s2.set)
        s2.grid(row=0, column=1, sticky="ns")

    def _build_disk_tab(self):
        tab = tk.Frame(self.tabs)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.tabs.add(tab, text="Disk Usage")
        self.tab_disk = tab

        controls = tk.Frame(tab, padx=12, pady=10)
        controls.grid(row=0, column=0, sticky="ew")

        self.lbl_path = tk.Label(controls, text="Path", font=("Adwaita Sans", 10, "bold"))
        self.lbl_path.pack(side="left")
        self.entry_path = tk.Entry(controls, textvariable=self.scan_path_var, font=("Adwaita Sans", 10), width=56)
        self.entry_path.pack(side="left", padx=(6, 8))

        self.btn_browse = self._add_btn(RoundedButton(controls, "Browse", self._browse_path, width=90))
        self.btn_browse.pack(side="left", padx=(0, 8))

        self.chk_hidden = tk.Checkbutton(controls, text="Show hidden", variable=self.show_hidden_var, onvalue=True, offvalue=False, font=("Adwaita Sans", 10), command=self._save_disk_settings)
        self.chk_hidden.pack(side="left", padx=(0, 8))

        self.btn_scan = self._add_btn(RoundedButton(controls, "Scan", self.scan_disk, width=90))
        self.btn_scan.pack(side="left")

        self.disk_summary = tk.Label(tab, text="", font=("Adwaita Sans", 10), anchor="w", padx=12)
        self.disk_summary.grid(row=1, column=0, sticky="ew")

        body = tk.Frame(tab, padx=12, pady=6)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.disk_body = body

        left = tk.LabelFrame(body, text="Top-Level Usage", padx=8, pady=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.disk_left = left

        self.top_tree = ttk.Treeview(left, columns=("name", "type", "size"), show="headings", style="App.Treeview")
        self.top_tree.heading("name", text="Name")
        self.top_tree.heading("type", text="Type")
        self.top_tree.heading("size", text="Size")
        self.top_tree.column("name", width=360, anchor="w")
        self.top_tree.column("type", width=80, anchor="w")
        self.top_tree.column("size", width=120, anchor="e")
        self.top_tree.grid(row=0, column=0, sticky="nsew")
        s3 = ttk.Scrollbar(left, orient="vertical", command=self.top_tree.yview)
        self.top_tree.configure(yscrollcommand=s3.set)
        s3.grid(row=0, column=1, sticky="ns")

        right = tk.LabelFrame(body, text="Largest Files", padx=8, pady=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.disk_right = right

        self.files_tree = ttk.Treeview(right, columns=("path", "size"), show="headings", style="App.Treeview")
        self.files_tree.heading("path", text="Path")
        self.files_tree.heading("size", text="Size")
        self.files_tree.column("path", width=480, anchor="w")
        self.files_tree.column("size", width=120, anchor="e")
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        s4 = ttk.Scrollbar(right, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=s4.set)
        s4.grid(row=0, column=1, sticky="ns")

    def _build_package_tab(self):
        tab = tk.Frame(self.tabs)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        self.tabs.add(tab, text="Package Audit")
        self.tab_pkg = tab

        controls = tk.Frame(tab, padx=12, pady=10)
        controls.grid(row=0, column=0, sticky="ew")

        self.btn_pkg_refresh = self._add_btn(RoundedButton(controls, "Refresh Audit", self.refresh_packages, width=126))
        self.btn_pkg_refresh.pack(side="left")

        self.btn_system_upgrade = self._add_btn(RoundedButton(controls, "Run System Upgrade", self._run_system_upgrade, width=172))
        self.btn_system_upgrade.pack(side="left", padx=(8, 0))

        self.btn_flatpak_upgrade = self._add_btn(RoundedButton(controls, "Run Flatpak Update", self._run_flatpak_upgrade, width=172))
        self.btn_flatpak_upgrade.pack(side="left", padx=(8, 0))

        self.btn_cleanup = self._add_btn(RoundedButton(controls, "Run Cleanup", self._run_cleanup, width=120))
        self.btn_cleanup.pack(side="left", padx=(8, 0))

        self.pkg_detected = tk.Label(controls, text="Managers: -", font=("Adwaita Sans", 10))
        self.pkg_detected.pack(side="left", padx=(12, 0))

        body = tk.Frame(tab, padx=12, pady=6)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.pkg_body = body

        self.pkg_text = tk.Text(body, wrap="word", font=("Adwaita Mono", 10), state="disabled")
        self.pkg_text.grid(row=0, column=0, sticky="nsew")
        s5 = ttk.Scrollbar(body, orient="vertical", command=self.pkg_text.yview)
        self.pkg_text.configure(yscrollcommand=s5.set)
        s5.grid(row=0, column=1, sticky="ns")

    def _save_service_settings(self):
        self.settings["service_search"] = self.service_search_var.get()
        self.settings["service_state_filter"] = self.service_state_var.get()
        save_settings(self.settings)

    def _save_disk_settings(self):
        self.settings["scan_path"] = self.scan_path_var.get()
        self.settings["show_hidden"] = bool(self.show_hidden_var.get())
        save_settings(self.settings)

    def _selected_service(self) -> str:
        sel = self.service_tree.selection()
        if not sel:
            return ""
        values = self.service_tree.item(sel[0], "values")
        return str(values[0]) if values else ""

    def _set_logs_text(self, text: str):
        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert("1.0", text)
        self.logs_text.configure(state="disabled")

    def refresh_services(self):
        self._save_service_settings()

        if not has_systemd():
            self.status_var.set("systemctl not available on this system")
            for node in self.service_tree.get_children():
                self.service_tree.delete(node)
            self._set_logs_text("systemd is not available on this system.")
            return

        self.status_var.set("Refreshing service list...")

        def task():
            rows = list_services(self.service_search_var.get(), self.service_state_var.get())
            self.root.after(0, lambda: self._render_services(rows))

        threading.Thread(target=task, daemon=True).start()

    def _render_services(self, rows):
        for node in self.service_tree.get_children():
            self.service_tree.delete(node)

        for i, row in enumerate(rows):
            self.service_tree.insert("", "end", iid=f"svc-{i}", values=(row.unit, row.load, row.active, row.sub, row.description))

        self.status_var.set(f"Loaded {len(rows)} services")

    def _do_service_action(self, action: str):
        unit = self._selected_service()
        if not unit:
            messagebox.showinfo("Service Action", "Select a service first.")
            return

        self.status_var.set(f"Running '{action}' on {unit}...")

        def task():
            ok, msg = run_service_action(action, unit)
            self.root.after(0, lambda: self._on_service_action_done(ok, msg))

        threading.Thread(target=task, daemon=True).start()

    def _on_service_action_done(self, ok: bool, msg: str):
        if ok:
            self.status_var.set(msg)
            self.refresh_services()
            return
        self.status_var.set("Service action failed")
        messagebox.showerror("Service Action Failed", msg)

    def show_selected_logs(self):
        unit = self._selected_service()
        if not unit:
            messagebox.showinfo("Service Logs", "Select a service first.")
            return

        self.status_var.set(f"Loading logs for {unit}...")

        def task():
            logs = read_service_logs(unit)
            self.root.after(0, lambda: self._on_logs_ready(unit, logs))

        threading.Thread(target=task, daemon=True).start()

    def _on_logs_ready(self, unit: str, logs: str):
        self._set_logs_text(logs)
        self.status_var.set(f"Showing logs for {unit}")

    def _browse_path(self):
        start = Path(self.scan_path_var.get()).expanduser()
        if not start.exists():
            start = Path.home()
        selected = filedialog.askdirectory(initialdir=str(start))
        if not selected:
            return
        self.scan_path_var.set(selected)
        self._save_disk_settings()

    def scan_disk(self):
        self._save_disk_settings()
        path = self.scan_path_var.get().strip()
        show_hidden = bool(self.show_hidden_var.get())

        self.status_var.set(f"Scanning disk usage for {path}...")

        def task():
            try:
                top, files, root = scan_disk(path, show_hidden=show_hidden)
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: self._on_disk_failed(str(exc)))
                return
            self.root.after(0, lambda: self._render_disk(root, top, files))

        threading.Thread(target=task, daemon=True).start()

    def _on_disk_failed(self, reason: str):
        self.status_var.set("Disk scan failed")
        messagebox.showerror("Disk Scan Failed", reason)

    def _render_disk(self, root: Path, top, files):
        for node in self.top_tree.get_children():
            self.top_tree.delete(node)
        for node in self.files_tree.get_children():
            self.files_tree.delete(node)

        for i, item in enumerate(top[:300]):
            self.top_tree.insert("", "end", iid=f"top-{i}", values=(item.path.name, item.item_type, human_size(item.size)))

        for i, item in enumerate(files[:300]):
            self.files_tree.insert("", "end", iid=f"file-{i}", values=(str(item.path), human_size(item.size)))

        self.disk_summary.configure(text=f"Scanned: {root} | Top-level items: {len(top)} | Largest files listed: {len(files)}")
        self.status_var.set("Disk scan complete")

    def refresh_packages(self):
        self.status_var.set("Running package audit...")

        def task():
            managers = detect_managers()
            results = audit_all()
            self.root.after(0, lambda: self._render_package_audit(managers, results))

        threading.Thread(target=task, daemon=True).start()

    def _render_package_audit(self, managers, results):
        self.managers = managers
        self.pkg_detected.configure(text=f"Managers: {', '.join(managers) if managers else 'none'}")

        lines = []
        for result in results:
            lines.append(f"[{result.manager}] {result.summary}")
            lines.append(result.details)
            lines.append("-" * 70)
        text = "\n".join(lines) if lines else "No supported package managers detected."

        self.pkg_text.configure(state="normal")
        self.pkg_text.delete("1.0", tk.END)
        self.pkg_text.insert("1.0", text)
        self.pkg_text.configure(state="disabled")

        self.btn_system_upgrade.set_enabled(bool(recommended_system_upgrade(self.managers)))
        self.btn_cleanup.set_enabled(bool(recommended_cleanup(self.managers)))
        self.btn_flatpak_upgrade.set_enabled("flatpak" in self.managers)

        self.status_var.set("Package audit complete")

    def _run_system_upgrade(self):
        cmd = recommended_system_upgrade(self.managers)
        if not cmd:
            messagebox.showinfo("System Upgrade", "No supported system package manager detected.")
            return
        ok, msg = launch_in_terminal(cmd, title="System Upgrade")
        if ok:
            self.status_var.set(msg)
        else:
            self.status_var.set("Failed to launch system upgrade")
            messagebox.showerror("System Upgrade", msg)

    def _run_flatpak_upgrade(self):
        if "flatpak" not in self.managers:
            messagebox.showinfo("Flatpak Update", "Flatpak is not detected on this system.")
            return
        ok, msg = launch_in_terminal("flatpak update", title="Flatpak Update")
        if ok:
            self.status_var.set(msg)
        else:
            self.status_var.set("Failed to launch Flatpak update")
            messagebox.showerror("Flatpak Update", msg)

    def _run_cleanup(self):
        cmd = recommended_cleanup(self.managers)
        if not cmd:
            messagebox.showinfo("Cleanup", "No cleanup command available for detected managers.")
            return
        ok, msg = launch_in_terminal(cmd, title="Package Cleanup")
        if ok:
            self.status_var.set(msg)
        else:
            self.status_var.set("Failed to launch cleanup")
            messagebox.showerror("Cleanup", msg)

    def apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            theme_name = "dark"

        self.theme_var.set(theme_name)
        self.settings["theme"] = theme_name
        save_settings(self.settings)

        p = THEMES[theme_name]

        self.style.configure("App.TCombobox", fieldbackground=p["entry"], foreground=p["entry_fg"], bordercolor=p["line"], padding=4, font=("Adwaita Sans", 10))
        self.style.map("App.TCombobox", fieldbackground=[("readonly", p["entry"])], foreground=[("readonly", p["entry_fg"])])
        self.style.configure("App.Treeview", background=p["card"], fieldbackground=p["card"], foreground=p["text"], rowheight=28, borderwidth=0, font=("Adwaita Sans", 10))
        self.style.map("App.Treeview", background=[("selected", p["select"])], foreground=[("selected", p["text"])])

        self.root.configure(bg=p["root"])
        self.header.configure(bg=p["root"])
        self.title.configure(bg=p["root"], fg=p["text"])
        self.subtitle.configure(bg=p["root"], fg=p["muted"])
        self.status.configure(bg=p["root"], fg=p["muted"])

        # Service tab widgets
        for w in (self.tab_systemd, self.logs_frame):
            w.configure(bg=p["panel"], fg=p["text"]) if isinstance(w, tk.LabelFrame) else w.configure(bg=p["panel"])
        self.lbl_search.configure(bg=p["panel"], fg=p["text"])
        self.lbl_state.configure(bg=p["panel"], fg=p["text"])
        self.entry_service_search.configure(bg=p["entry"], fg=p["entry_fg"], insertbackground=p["entry_fg"], relief="flat")
        self.logs_text.configure(bg=p["card"], fg=p["text"], insertbackground=p["text"])

        # Disk tab widgets
        self.tab_disk.configure(bg=p["panel"])
        self.lbl_path.configure(bg=p["panel"], fg=p["text"])
        self.entry_path.configure(bg=p["entry"], fg=p["entry_fg"], insertbackground=p["entry_fg"], relief="flat")
        self.chk_hidden.configure(bg=p["panel"], fg=p["text"], selectcolor=p["panel"], activebackground=p["panel"], activeforeground=p["text"])
        self.disk_summary.configure(bg=p["panel"], fg=p["muted"])
        self.disk_body.configure(bg=p["panel"])
        self.disk_left.configure(bg=p["panel"], fg=p["text"])
        self.disk_right.configure(bg=p["panel"], fg=p["text"])

        # Package tab widgets
        self.tab_pkg.configure(bg=p["panel"])
        self.pkg_body.configure(bg=p["panel"])
        self.pkg_detected.configure(bg=p["panel"], fg=p["muted"])
        self.pkg_text.configure(bg=p["card"], fg=p["text"], insertbackground=p["text"])

        for btn in self.round_buttons:
            btn.configure_theme(p, btn.master.cget("bg"))

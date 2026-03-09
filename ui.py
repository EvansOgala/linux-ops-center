from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

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
from gtk_style import install_material_smooth_css


class LinuxOpsCenterApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.evans.LinuxOpsCenter")
        self.window: Gtk.ApplicationWindow | None = None

        self.settings = load_settings()
        self.theme_values = ["dark", "light"]
        self.service_state_values = ["all", "running", "failed", "inactive"]
        self.css_provider = None

        self.managers: list[str] = []
        self.service_row_units: dict[str, str] = {}

        self.theme_dropdown: Gtk.DropDown | None = None
        self.status_label: Gtk.Label | None = None

        self.service_search_entry: Gtk.Entry | None = None
        self.service_state_dropdown: Gtk.DropDown | None = None
        self.service_list: Gtk.ListBox | None = None
        self.logs_view: Gtk.TextView | None = None

        self.path_entry: Gtk.Entry | None = None
        self.hidden_switch: Gtk.Switch | None = None
        self.disk_summary_label: Gtk.Label | None = None
        self.disk_top_view: Gtk.TextView | None = None
        self.disk_files_view: Gtk.TextView | None = None

        self.pkg_detected_label: Gtk.Label | None = None
        self.pkg_view: Gtk.TextView | None = None

        self.btn_system_upgrade: Gtk.Button | None = None
        self.btn_flatpak_upgrade: Gtk.Button | None = None
        self.btn_cleanup: Gtk.Button | None = None

    def do_activate(self):
        if self.window is None:
            self._build_ui()
            self.refresh_services()
            self.scan_disk()
            self.refresh_packages()
        self.window.present()

    def _build_ui(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Linux Ops Center")
        self.window.set_default_size(1300, 860)
        self.css_provider = install_material_smooth_css(self.window)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(12)
        root.set_margin_bottom(12)
        root.set_margin_start(12)
        root.set_margin_end(12)
        self.window.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(header)

        title_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.append(title_wrap)

        title = Gtk.Label(label="Linux Ops Center")
        title.set_xalign(0.0)
        title.add_css_class("title-2")
        title_wrap.append(title)

        subtitle = Gtk.Label(label="Systemd dashboard, disk usage visualizer, package audit")
        subtitle.set_xalign(0.0)
        subtitle.add_css_class("dim-label")
        title_wrap.append(subtitle)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)

        self.theme_dropdown = Gtk.DropDown.new_from_strings(self.theme_values)
        self._set_dropdown_value(self.theme_dropdown, self.theme_values, self.settings.get("theme", "dark"))
        self.theme_dropdown.connect("notify::selected", self._on_theme_changed)
        header.append(self.theme_dropdown)

        notebook = Gtk.Notebook()
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)
        root.append(notebook)

        notebook.append_page(self._build_services_tab(), Gtk.Label(label="Systemd"))
        notebook.append_page(self._build_disk_tab(), Gtk.Label(label="Disk"))
        notebook.append_page(self._build_packages_tab(), Gtk.Label(label="Packages"))

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0.0)
        self.status_label.add_css_class("dim-label")
        root.append(self.status_label)

        self._apply_theme(self.settings.get("theme", "dark"))

    def _build_services_tab(self) -> Gtk.Widget:
        tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tab.set_margin_top(10)
        tab.set_margin_bottom(10)
        tab.set_margin_start(10)
        tab.set_margin_end(10)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tab.append(controls)

        controls.append(Gtk.Label(label="Search"))
        self.service_search_entry = Gtk.Entry()
        self.service_search_entry.set_hexpand(True)
        self.service_search_entry.set_text(str(self.settings.get("service_search", "")))
        self.service_search_entry.connect("activate", lambda _e: self.refresh_services())
        controls.append(self.service_search_entry)

        controls.append(Gtk.Label(label="State"))
        self.service_state_dropdown = Gtk.DropDown.new_from_strings(self.service_state_values)
        self._set_dropdown_value(
            self.service_state_dropdown,
            self.service_state_values,
            str(self.settings.get("service_state_filter", "all")),
        )
        self.service_state_dropdown.connect("notify::selected", lambda _d, _p: self.refresh_services())
        controls.append(self.service_state_dropdown)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda _b: self.refresh_services())
        controls.append(refresh_btn)

        split = Gtk.Paned.new(Gtk.Orientation.VERTICAL)
        split.set_hexpand(True)
        split.set_vexpand(True)
        tab.append(split)

        services_frame = Gtk.Frame(label="Services")
        split.set_start_child(services_frame)

        service_scroller = Gtk.ScrolledWindow()
        service_scroller.set_hexpand(True)
        service_scroller.set_vexpand(True)
        services_frame.set_child(service_scroller)

        self.service_list = Gtk.ListBox()
        self.service_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.service_list.connect("row-selected", self._on_service_row_selected)
        service_scroller.set_child(self.service_list)

        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab.append(action_row)
        for action in ("start", "stop", "restart", "enable", "disable"):
            btn = Gtk.Button(label=action.title())
            btn.connect("clicked", lambda _b, a=action: self._do_service_action(a))
            action_row.append(btn)

        logs_btn = Gtk.Button(label="Show Logs")
        logs_btn.connect("clicked", lambda _b: self.show_selected_logs())
        action_row.append(logs_btn)

        logs_frame = Gtk.Frame(label="Logs")
        split.set_end_child(logs_frame)

        logs_scroller = Gtk.ScrolledWindow()
        logs_scroller.set_hexpand(True)
        logs_scroller.set_vexpand(True)
        logs_frame.set_child(logs_scroller)

        self.logs_view = Gtk.TextView()
        self.logs_view.set_editable(False)
        self.logs_view.set_monospace(True)
        logs_scroller.set_child(self.logs_view)

        return tab

    def _build_disk_tab(self) -> Gtk.Widget:
        tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tab.set_margin_top(10)
        tab.set_margin_bottom(10)
        tab.set_margin_start(10)
        tab.set_margin_end(10)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tab.append(controls)

        controls.append(Gtk.Label(label="Path"))
        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.set_text(str(self.settings.get("scan_path", str(Path.home()))))
        self.path_entry.connect("activate", lambda _e: self.scan_disk())
        controls.append(self.path_entry)

        controls.append(Gtk.Label(label="Show hidden"))
        self.hidden_switch = Gtk.Switch()
        self.hidden_switch.set_active(bool(self.settings.get("show_hidden", False)))
        self.hidden_switch.connect("notify::active", self._on_hidden_switch_changed)
        controls.append(self.hidden_switch)

        scan_btn = Gtk.Button(label="Scan")
        scan_btn.connect("clicked", lambda _b: self.scan_disk())
        controls.append(scan_btn)

        self.disk_summary_label = Gtk.Label(label="")
        self.disk_summary_label.set_xalign(0.0)
        self.disk_summary_label.add_css_class("dim-label")
        tab.append(self.disk_summary_label)

        split = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        split.set_hexpand(True)
        split.set_vexpand(True)
        tab.append(split)

        top_frame = Gtk.Frame(label="Top-Level Usage")
        split.set_start_child(top_frame)

        top_scroller = Gtk.ScrolledWindow()
        top_scroller.set_hexpand(True)
        top_scroller.set_vexpand(True)
        top_frame.set_child(top_scroller)

        self.disk_top_view = Gtk.TextView()
        self.disk_top_view.set_editable(False)
        self.disk_top_view.set_monospace(True)
        top_scroller.set_child(self.disk_top_view)

        files_frame = Gtk.Frame(label="Largest Files")
        split.set_end_child(files_frame)

        files_scroller = Gtk.ScrolledWindow()
        files_scroller.set_hexpand(True)
        files_scroller.set_vexpand(True)
        files_frame.set_child(files_scroller)

        self.disk_files_view = Gtk.TextView()
        self.disk_files_view.set_editable(False)
        self.disk_files_view.set_monospace(True)
        files_scroller.set_child(self.disk_files_view)

        return tab

    def _build_packages_tab(self) -> Gtk.Widget:
        tab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tab.set_margin_top(10)
        tab.set_margin_bottom(10)
        tab.set_margin_start(10)
        tab.set_margin_end(10)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab.append(actions)

        refresh_btn = Gtk.Button(label="Refresh Audit")
        refresh_btn.connect("clicked", lambda _b: self.refresh_packages())
        actions.append(refresh_btn)

        self.btn_system_upgrade = Gtk.Button(label="System Upgrade")
        self.btn_system_upgrade.connect("clicked", lambda _b: self._run_system_upgrade())
        actions.append(self.btn_system_upgrade)

        self.btn_flatpak_upgrade = Gtk.Button(label="Flatpak Update")
        self.btn_flatpak_upgrade.connect("clicked", lambda _b: self._run_flatpak_upgrade())
        actions.append(self.btn_flatpak_upgrade)

        self.btn_cleanup = Gtk.Button(label="Cleanup")
        self.btn_cleanup.connect("clicked", lambda _b: self._run_cleanup())
        actions.append(self.btn_cleanup)

        self.pkg_detected_label = Gtk.Label(label="Managers: -")
        self.pkg_detected_label.set_xalign(0.0)
        self.pkg_detected_label.add_css_class("dim-label")
        tab.append(self.pkg_detected_label)

        pkg_scroller = Gtk.ScrolledWindow()
        pkg_scroller.set_hexpand(True)
        pkg_scroller.set_vexpand(True)
        tab.append(pkg_scroller)

        self.pkg_view = Gtk.TextView()
        self.pkg_view.set_editable(False)
        self.pkg_view.set_monospace(True)
        pkg_scroller.set_child(self.pkg_view)

        return tab

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.set_text(text)

    def _set_text(self, view: Gtk.TextView | None, text: str):
        if view is None:
            return
        view.get_buffer().set_text(text)

    def _on_theme_changed(self, dropdown: Gtk.DropDown, _param):
        self._apply_theme(self._get_dropdown_value(dropdown, self.theme_values))

    def _apply_theme(self, theme_name: str):
        if theme_name not in {"dark", "light"}:
            theme_name = "dark"
        self.settings["theme"] = theme_name
        save_settings(self.settings)

        gtk_settings = Gtk.Settings.get_default()
        if gtk_settings is not None:
            gtk_settings.set_property("gtk-application-prefer-dark-theme", theme_name == "dark")

    def _save_service_settings(self):
        if self.service_search_entry is not None:
            self.settings["service_search"] = self.service_search_entry.get_text().strip()
        if self.service_state_dropdown is not None:
            self.settings["service_state_filter"] = self._get_dropdown_value(
                self.service_state_dropdown,
                self.service_state_values,
            )
        save_settings(self.settings)

    def _save_disk_settings(self):
        if self.path_entry is not None:
            self.settings["scan_path"] = self.path_entry.get_text().strip()
        if self.hidden_switch is not None:
            self.settings["show_hidden"] = bool(self.hidden_switch.get_active())
        save_settings(self.settings)

    def _on_hidden_switch_changed(self, _switch: Gtk.Switch, _param):
        self._save_disk_settings()

    def _selected_service(self) -> str:
        if self.service_list is None:
            return ""
        row = self.service_list.get_selected_row()
        if row is None:
            return ""
        return self.service_row_units.get(row.get_name() or "", "")

    def refresh_services(self):
        if not has_systemd():
            self._set_text(self.logs_view, "systemctl is not available on this machine.")
            self._set_status("systemctl not found")
            return

        self._save_service_settings()
        search = self.settings.get("service_search", "")
        state_filter = self.settings.get("service_state_filter", "all")

        self._set_status("Refreshing services...")

        def task():
            rows = list_services(str(search), str(state_filter))
            GLib.idle_add(self._render_services, rows)

        threading.Thread(target=task, daemon=True).start()

    def _render_services(self, rows):
        if self.service_list is None:
            return False

        self._clear_listbox(self.service_list)
        self.service_row_units.clear()

        for idx, row_data in enumerate(rows):
            row = Gtk.ListBoxRow()
            text = f"{row_data.unit} | {row_data.active}/{row_data.sub} | {row_data.description}"
            label = Gtk.Label(label=text, xalign=0.0)
            label.set_selectable(False)
            row.set_child(label)
            row_key = f"service-{idx}"
            row.set_name(row_key)
            self.service_row_units[row_key] = row_data.unit
            self.service_list.append(row)

        self._set_status(f"Loaded {len(rows)} services")
        return False

    def _on_service_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None):
        if row is None:
            return
        unit = self.service_row_units.get(row.get_name() or "", "")
        if unit:
            self._set_status(f"Selected service: {unit}")

    def _do_service_action(self, action: str):
        unit = self._selected_service()
        if not unit:
            self._set_status("Select a service first")
            return

        self._set_status(f"Running {action} on {unit}...")

        def task():
            ok, msg = run_service_action(action, unit)
            GLib.idle_add(self._on_service_action_done, ok, msg)

        threading.Thread(target=task, daemon=True).start()

    def _on_service_action_done(self, ok: bool, msg: str):
        self._set_status(msg)
        if not ok:
            self._set_text(self.logs_view, msg)
        self.refresh_services()
        return False

    def show_selected_logs(self):
        unit = self._selected_service()
        if not unit:
            self._set_status("Select a service first")
            return

        self._set_status(f"Loading logs for {unit}...")

        def task():
            logs = read_service_logs(unit)
            GLib.idle_add(self._on_logs_ready, unit, logs)

        threading.Thread(target=task, daemon=True).start()

    def _on_logs_ready(self, unit: str, logs: str):
        self._set_text(self.logs_view, logs)
        self._set_status(f"Logs loaded for {unit}")
        return False

    def scan_disk(self):
        self._save_disk_settings()
        path = str(self.settings.get("scan_path", str(Path.home()))).strip()
        show_hidden = bool(self.settings.get("show_hidden", False))

        self._set_status("Scanning disk...")

        def task():
            try:
                top, files, root = scan_disk(path, show_hidden=show_hidden)
                GLib.idle_add(self._render_disk, root, top, files)
            except Exception as exc:  # noqa: BLE001
                GLib.idle_add(self._on_disk_failed, str(exc))

        threading.Thread(target=task, daemon=True).start()

    def _on_disk_failed(self, reason: str):
        self._set_status(f"Disk scan failed: {reason}")
        return False

    def _render_disk(self, root: Path, top, files):
        top_lines = [f"{item.item_type:>4}  {human_size(item.size):>10}  {item.path.name}" for item in top[:250]]
        file_lines = [f"{human_size(item.size):>10}  {item.path}" for item in files[:250]]

        self._set_text(self.disk_top_view, "\n".join(top_lines) if top_lines else "No data")
        self._set_text(self.disk_files_view, "\n".join(file_lines) if file_lines else "No data")

        if self.disk_summary_label is not None:
            self.disk_summary_label.set_text(
                f"Scanned: {root} | Top-level items: {len(top)} | Largest files listed: {len(files)}"
            )
        self._set_status("Disk scan complete")
        return False

    def refresh_packages(self):
        self._set_status("Running package audit...")

        def task():
            managers = detect_managers()
            results = audit_all()
            GLib.idle_add(self._render_package_audit, managers, results)

        threading.Thread(target=task, daemon=True).start()

    def _render_package_audit(self, managers, results):
        self.managers = list(managers)
        if self.pkg_detected_label is not None:
            self.pkg_detected_label.set_text(f"Managers: {', '.join(self.managers) if self.managers else 'none'}")

        lines: list[str] = []
        for result in results:
            lines.append(f"[{result.manager}] {result.summary}")
            lines.append(result.details)
            lines.append("-" * 72)
        text = "\n".join(lines) if lines else "No supported package managers detected."
        self._set_text(self.pkg_view, text)

        if self.btn_system_upgrade is not None:
            self.btn_system_upgrade.set_sensitive(bool(recommended_system_upgrade(self.managers)))
        if self.btn_cleanup is not None:
            self.btn_cleanup.set_sensitive(bool(recommended_cleanup(self.managers)))
        if self.btn_flatpak_upgrade is not None:
            self.btn_flatpak_upgrade.set_sensitive("flatpak" in self.managers)

        self._set_status("Package audit complete")
        return False

    def _run_system_upgrade(self):
        cmd = recommended_system_upgrade(self.managers)
        if not cmd:
            self._set_status("No supported system package manager detected")
            return
        ok, msg = launch_in_terminal(cmd, title="System Upgrade")
        self._set_status(msg if ok else f"System upgrade launch failed: {msg}")

    def _run_flatpak_upgrade(self):
        if "flatpak" not in self.managers:
            self._set_status("Flatpak is not detected on this system")
            return
        ok, msg = launch_in_terminal("flatpak update", title="Flatpak Update")
        self._set_status(msg if ok else f"Flatpak launch failed: {msg}")

    def _run_cleanup(self):
        cmd = recommended_cleanup(self.managers)
        if not cmd:
            self._set_status("No cleanup command available")
            return
        ok, msg = launch_in_terminal(cmd, title="Package Cleanup")
        self._set_status(msg if ok else f"Cleanup launch failed: {msg}")

    @staticmethod
    def _set_dropdown_value(dropdown: Gtk.DropDown, values: list[str], value: str):
        try:
            idx = values.index(value)
        except ValueError:
            idx = 0
        dropdown.set_selected(idx)

    @staticmethod
    def _get_dropdown_value(dropdown: Gtk.DropDown, values: list[str]) -> str:
        idx = int(dropdown.get_selected())
        if 0 <= idx < len(values):
            return values[idx]
        return values[0]

    @staticmethod
    def _clear_listbox(box: Gtk.ListBox):
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

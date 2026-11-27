#!/usr/bin/env python3
"""Hacker Cam: desktop app for the hacker video-call effects.

Runs on macOS, Windows and Linux. Lives in the menu bar (macOS) or the
system tray (Windows/Linux): its menu has every effect. "Open window" shows a
live preview of what the call sees, plus settings. The global Ctrl+Alt hotkeys
keep working while the call app is focused. In Zoom/Teams/Meet, pick
"OBS Virtual Camera".

    python app.py            # starts in the menu bar / tray
    python app.py --window   # also opens the window
"""
import os
import sys
import threading

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QPlainTextEdit, QPushButton,
    QMessageBox, QRadioButton, QScrollArea, QSizePolicy, QSlider, QSystemTrayIcon, QVBoxLayout, QWidget,
)

import hacker_intro as hi
import telemetry

__version__ = "1.0.2"
GREEN = "#46ff46"
STYLE = """
QWidget { background: #070b07; color: #b8f5b8;
          font-family: "JetBrains Mono", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
          font-size: 13px; }
QGroupBox { border: 1px solid #1f5f1f; border-radius: 6px; margin-top: 14px;
            padding: 12px 8px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px;
                   color: #46ff46; font-weight: bold; }
QPushButton { background: #0d160d; border: 1px solid #2d7a2d; border-radius: 4px;
              padding: 7px 10px; text-align: left; }
QPushButton:hover { background: #143014; border-color: #46ff46; }
QPushButton:pressed { background: #1d4a1d; }
QPushButton:checked { background: #1f5f1f; color: #eaffea; border-color: #46ff46; }
QPushButton:disabled { color: #3d6b3d; border-color: #1a3a1a; }
QLineEdit, QComboBox { background: #0d160d; border: 1px solid #2d7a2d; border-radius: 4px;
                       padding: 5px; }
QLineEdit:focus, QComboBox:focus { border-color: #46ff46; }
QComboBox QAbstractItemView { background: #0d160d; selection-background-color: #1f5f1f; }
QPlainTextEdit { background: #040704; border: 1px solid #143014; color: #6fbf6f; font-size: 11px; }
QLabel#preview { background: #000; border: 1px solid #1f5f1f; }
QLabel#hint { color: #4f8f4f; font-size: 11px; }
QLabel#status { font-weight: bold; padding: 4px 2px; }
QSlider::groove:horizontal { height: 4px; background: #1f5f1f; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -6px 0; background: #46ff46; border-radius: 7px; }
QScrollArea { border: none; }
QToolTip { background: #0d160d; color: #b8f5b8; border: 1px solid #46ff46; }
QRadioButton, QCheckBox { spacing: 8px; padding: 3px 0; }
QRadioButton::indicator { width: 12px; height: 12px; border: 1px solid #2d7a2d;
                          border-radius: 7px; background: #0d160d; }
QCheckBox::indicator { width: 12px; height: 12px; border: 1px solid #2d7a2d;
                       border-radius: 2px; background: #0d160d; }
QRadioButton::indicator:checked, QCheckBox::indicator:checked { background: #46ff46;
                                                                 border-color: #46ff46; }
QRadioButton::indicator:hover, QCheckBox::indicator:hover { border-color: #46ff46; }
QScrollBar:vertical { background: #070b07; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #1f5f1f; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #2d7a2d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QMenu { background: #0b120b; border: 1px solid #2d7a2d; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 22px; }
QMenu::item:selected { background: #1f5f1f; color: #eaffea; }
QMenu::item:disabled { color: #6f9f6f; }
QMenu::separator { height: 1px; background: #1f5f1f; margin: 4px 8px; }
"""

LAUNCH_ACTIONS = [("Play intro", "intro"), ("Black screen, wait for entrance", "entrance"),
                  ("Nothing (show webcam)", "none")]


def hotkey_hint(letter):
    return ("⌃⌥" if sys.platform == "darwin" else "Ctrl+Alt+") + letter.upper()


def list_cameras():
    """Camera names in system order (matches OpenCV's index on most systems)."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
        return [d.description() for d in QMediaDevices.videoInputs()]
    except Exception:
        return []


def make_icon(live):
    """Menu bar / tray icon: a terminal prompt, green with a red REC dot when live."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = QColor(GREEN if live else "#8fa58f")
    p.setPen(QPen(color, 5))
    p.setBrush(QColor(0, 0, 0, 210))
    p.drawRoundedRect(4, 8, 56, 48, 9, 9)
    p.setFont(QFont("Menlo" if sys.platform == "darwin" else "Consolas", 22, QFont.Bold))
    p.drawText(pm.rect().adjusted(0, 2, 0, 0), Qt.AlignCenter, ">_")
    if live:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ff3b3b"))
        p.drawEllipse(46, 2, 16, 16)
    p.end()
    return QIcon(pm)


class PreviewLabel(QLabel):
    """Shows frames scaled to fit, keeping 16:9."""

    def __init__(self):
        super().__init__()
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = None

    def show_frame(self, frame):
        h, w = frame.shape[:2]
        img = QImage(np.ascontiguousarray(frame).data, w, h, 3 * w, QImage.Format_BGR888).copy()
        self._pixmap = QPixmap.fromImage(img)
        self._rescale()

    def _rescale(self):
        if self._pixmap is not None:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation))

    def resizeEvent(self, event):
        self._rescale()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hacker Cam")
        self.settings = QSettings("HackerCam", "HackerCam")
        self._log_lock = threading.Lock()
        self._pending_log = []
        self.hotkeys = None
        self.tray = None
        self._quitting = False
        self._told_about_tray = False

        s = self.settings
        self.engine = hi.Engine(
            name=s.value("name", "Anonymous"), title=s.value("title", "Operator"),
            duration_scale=float(s.value("duration_scale", 1.0)), log=self._log)

        # Anonymous usage stats: off until the user agrees (see telemetry.py).
        if not s.value("install_id"):
            s.setValue("install_id", telemetry.Telemetry.new_install_id())
        self.stats = telemetry.Telemetry(s.value("install_id"), __version__,
                                         enabled=s.value("telemetry", False, type=bool))
        self.session = telemetry.Session()
        self.engine.on_action = lambda action: self.stats.capture("effect_used", effect=action)

        self._build_ui()
        self._load_initial_state()
        self._build_tray()
        self.stats.capture("app_started", output_ok=self.engine.vcam is not None,
                           camera_ok=bool(self.engine.webcam and self.engine.webcam.ok),
                           tray=self.tray is not None)
        if telemetry.available() and s.value("telemetry") is None:
            QTimer.singleShot(1200, self._ask_telemetry)

        self.thread = threading.Thread(target=self._run_engine, daemon=True)
        self.thread.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    # --- layout ------------------------------------------------------------

    def _action_row(self, text, letter=None, checkable=False, on_click=None, tip=""):
        row = QHBoxLayout()
        btn = QPushButton(text)
        btn.setCheckable(checkable)
        btn.setToolTip(tip)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if on_click:
            btn.clicked.connect(on_click)
        row.addWidget(btn)
        hint = QLabel(hotkey_hint(letter) if letter else "")   # keeps rows equal width
        hint.setObjectName("hint")
        hint.setFixedWidth(80)
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(hint)
        return row, btn

    def _build_ui(self):
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Left: preview, status, log.
        left = QVBoxLayout()
        title = QLabel("HACKER CAM")
        title.setStyleSheet(f"color: {GREEN}; font-size: 20px; font-weight: bold; letter-spacing: 4px;")
        left.addWidget(title)
        self.preview = PreviewLabel()
        left.addWidget(self.preview, 1)
        self.status = QLabel("Starting ...")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(300)
        self.log_view.setFixedHeight(110)
        left.addWidget(self.log_view)
        layout.addLayout(left, 3)

        # Right: controls in a scroll area.
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.setContentsMargins(0, 0, 6, 0)

        # Output
        box = QGroupBox("OUTPUT")
        f = QFormLayout(box)
        self.camera_combo = QComboBox()
        self.camera_combo.activated.connect(self._camera_chosen)
        f.addRow("Webcam", self.camera_combo)
        self.output_btn = QPushButton("Send to virtual camera")
        self.output_btn.setCheckable(True)
        self.output_btn.setToolTip("Sends the picture to 'OBS Virtual Camera'.\n"
                                   "Select that camera in Zoom, Teams, Meet, ...")
        self.output_btn.clicked.connect(self._output_toggled)
        f.addRow(self.output_btn)
        col.addWidget(box)

        # Identity
        box = QGroupBox("IDENTITY")
        f = QFormLayout(box)
        self.name_edit = QLineEdit(self.engine.name)
        self.title_edit = QLineEdit(self.engine.title)
        self.name_edit.editingFinished.connect(self._identity_changed)
        self.title_edit.editingFinished.connect(self._identity_changed)
        f.addRow("Name", self.name_edit)
        f.addRow("Title", self.title_edit)
        col.addWidget(box)

        # Moments
        box = QGroupBox("MOMENTS")
        v = QVBoxLayout(box)
        cmd = self.engine.command
        row, _ = self._action_row("▶  Play intro", "h", on_click=lambda: cmd("replay"),
                                  tip="Matrix rain → breach log → ACCESS GRANTED → your name")
        v.addLayout(row)
        row, _ = self._action_row("■  Black screen", on_click=self._arm_entrance,
                                  tip="Go to a black INCOMING SIGNAL screen and wait for the entrance")
        v.addLayout(row)
        row, _ = self._action_row("⚡  Entrance", "e", on_click=lambda: cmd("entrance"),
                                  tip="Assemble into view out of falling particles")
        v.addLayout(row)
        row, _ = self._action_row("◎  Biometric scan", "b", on_click=lambda: cmd("scan"),
                                  tip="Face scan ending in BIOMETRIC MATCH")
        v.addLayout(row)
        row, self.away_btn = self._action_row("⏸  Away screen", "a", checkable=True,
                                              on_click=lambda: cmd("away"),
                                              tip="SESSION SUSPENDED screen with an away timer")
        v.addLayout(row)
        col.addWidget(box)

        # Looks
        box = QGroupBox("LOOKS")
        v = QVBoxLayout(box)
        row, self.filter_btn = self._action_row("Hacker filter", "g", checkable=True,
                                                on_click=lambda: cmd("filter"),
                                                tip="Green phosphor, scanlines, static, glitch bursts")
        v.addLayout(row)
        row, self.holo_btn = self._action_row("Hologram", "o", checkable=True,
                                              on_click=lambda: cmd("hologram"),
                                              tip="Translucent flickering cyan projection")
        v.addLayout(row)
        col.addWidget(box)

        # Background
        box = QGroupBox("BACKGROUND")
        v = QVBoxLayout(box)
        self.bg_group = QButtonGroup(self)
        self.bg_radios = {}
        for value, label, letter in ((None, "Real room", None), ("matrix", "Matrix rain", "m"),
                                     ("trace", "Global trace map", "t")):
            row = QHBoxLayout()
            rb = QRadioButton(label)
            self.bg_group.addButton(rb)
            self.bg_radios[value] = rb
            rb.toggled.connect(lambda checked, v=value: checked and self._set_background(v))
            row.addWidget(rb)
            if letter:
                hint = QLabel(hotkey_hint(letter))
                hint.setObjectName("hint")
                row.addWidget(hint, 0, Qt.AlignRight)
            v.addLayout(row)
        col.addWidget(box)

        # Options
        box = QGroupBox("OPTIONS")
        f = QFormLayout(box)
        self.launch_combo = QComboBox()
        for label, _ in LAUNCH_ACTIONS:
            self.launch_combo.addItem(label)
        self.launch_combo.currentIndexChanged.connect(
            lambda i: self.settings.setValue("launch_action", LAUNCH_ACTIONS[i][1]))
        f.addRow("On launch", self.launch_combo)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 150)
        self.speed_slider.setValue(int(self.engine.duration_scale * 100))
        self.speed_slider.setToolTip("Intro length: left = faster, right = slower")
        self.speed_slider.valueChanged.connect(self._speed_changed)
        f.addRow("Intro length", self.speed_slider)
        self.hotkeys_check = QCheckBox(f"Global hotkeys ({hotkey_hint('…')})")
        self.hotkeys_check.setToolTip("Work while the call app is focused.\n"
                                      "macOS: allow Input Monitoring for this app/terminal.")
        self.hotkeys_check.toggled.connect(self._hotkeys_toggled)
        f.addRow(self.hotkeys_check)
        self.window_check = QCheckBox("Open this window at launch")
        self.window_check.setChecked(self.settings.value("show_window", False, type=bool))
        self.window_check.toggled.connect(lambda on: self.settings.setValue("show_window", on))
        f.addRow(self.window_check)
        self.stats_check = QCheckBox("Share anonymous usage stats")
        self.stats_check.setToolTip("Which effects get used, app version and OS.\n"
                                    "Never video, images, your name or anything you type.")
        self.stats_check.setChecked(self.settings.value("telemetry", False, type=bool))
        self.stats_check.toggled.connect(self._telemetry_toggled)
        self.stats_check.setVisible(telemetry.available())
        f.addRow(self.stats_check)
        col.addWidget(box)
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 2)

        self.setCentralWidget(root)
        self.resize(1280, 760)

    # --- startup -----------------------------------------------------------

    def _load_initial_state(self):
        s = self.settings
        names = list_cameras()
        count = max(len(names), 1)
        for i in range(count):
            name = names[i] if i < len(names) else "Default camera"
            label = f"{i}: {name}"
            if "virtual" in name.lower():
                label += "  (not this one)"
            self.camera_combo.addItem(label, i)
        index = int(s.value("camera_index", 0))
        if index >= count or "virtual" in self.camera_combo.itemText(index).lower():
            index = next((i for i in range(count)
                          if "virtual" not in self.camera_combo.itemText(i).lower()), 0)
        self.camera_combo.setCurrentIndex(index)
        self.engine.open_camera(index)

        self.engine.filter_on = s.value("filter", False, type=bool)
        self.engine.holo_on = s.value("hologram", False, type=bool)
        bg = s.value("background", "") or None
        self.engine.background = bg if bg in ("matrix", "trace") else None

        if s.value("output", True, type=bool):
            self.engine.set_output(True)

        launch = s.value("launch_action", "intro")
        keys = [k for _, k in LAUNCH_ACTIONS]
        self.launch_combo.setCurrentIndex(keys.index(launch) if launch in keys else 0)
        if launch == "intro":
            self.engine.command("replay")
        elif launch == "entrance":
            self.engine.entrance.arm()

        self.hotkeys_check.setChecked(s.value("hotkeys", True, type=bool))

    def _menu_action(self, menu, text, letter=None, checkable=False, slot=None):
        if letter is None:
            label = text
        elif sys.platform == "darwin":
            # A tab would make the native macOS menu register a real shortcut
            # (double-firing with the global hotkey), so keep the hint as text.
            label = f"{text}      {hotkey_hint(letter)}"
        else:
            label = f"{text}\t{hotkey_hint(letter)}"      # right-aligned column
        action = QAction(label, menu)
        action.setCheckable(checkable)
        if slot is not None:
            action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_tray(self):
        """Menu bar (macOS) / system tray (Windows, Linux) icon with every effect."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._log("[!] No menu bar / system tray here: using the window only.")
            return
        self.icon_live, self.icon_idle = make_icon(True), make_icon(False)
        cmd = self.engine.command
        menu = QMenu()
        self.menu_status = menu.addAction("Starting ...")
        self.menu_status.setEnabled(False)
        self.act_output = self._menu_action(menu, "Send to virtual camera", checkable=True,
                                            slot=lambda on: self._output_toggled(on))
        menu.addSeparator()
        self._menu_action(menu, "▶  Play intro", "h", slot=lambda *_: cmd("replay"))
        self._menu_action(menu, "■  Black screen", slot=lambda *_: self._arm_entrance())
        self._menu_action(menu, "⚡  Entrance", "e", slot=lambda *_: cmd("entrance"))
        self._menu_action(menu, "◎  Biometric scan", "b", slot=lambda *_: cmd("scan"))
        self.act_away = self._menu_action(menu, "⏸  Away screen", "a", checkable=True,
                                          slot=lambda *_: cmd("away"))
        menu.addSeparator()
        self.act_filter = self._menu_action(menu, "Hacker filter", "g", checkable=True,
                                            slot=lambda *_: cmd("filter"))
        self.act_holo = self._menu_action(menu, "Hologram", "o", checkable=True,
                                          slot=lambda *_: cmd("hologram"))

        bg_menu = menu.addMenu("Background")
        group = QActionGroup(bg_menu)
        group.setExclusive(True)
        self.act_bg = {}
        for value, label, letter in ((None, "Real room", None), ("matrix", "Matrix rain", "m"),
                                     ("trace", "Global trace map", "t")):
            a = self._menu_action(bg_menu, label, letter, checkable=True,
                                  slot=lambda *_, v=value: self._set_background(v))
            group.addAction(a)
            self.act_bg[value] = a

        cam_menu = menu.addMenu("Webcam")
        group = QActionGroup(cam_menu)
        group.setExclusive(True)
        self.act_cams = []
        for i in range(self.camera_combo.count()):
            a = self._menu_action(cam_menu, self.camera_combo.itemText(i), checkable=True,
                                  slot=lambda *_, i=i: self._select_camera(i))
            group.addAction(a)
            self.act_cams.append(a)

        menu.addSeparator()
        self._menu_action(menu, "Open window ...", slot=lambda *_: self.show_window())
        self._menu_action(menu, "Quit Hacker Cam", "q", slot=lambda *_: self.quit_app())

        self.tray_menu = menu                     # keep a reference: Qt doesn't own it
        self.tray = QSystemTrayIcon(self.icon_idle, self)
        self.tray.setToolTip("Hacker Cam")
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._tray_live = False

    def _tray_activated(self, reason):
        # Windows/Linux: double-click opens the window (right-click shows the menu).
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._quitting = True
        self.close()
        QApplication.quit()

    def _run_engine(self):
        try:
            self.engine.run()
        except Exception as e:  # keep the UI alive and show what happened
            self._log(f"[!] Engine stopped: {e!r}")
            self.engine.stop()

    # --- handlers ----------------------------------------------------------

    def _log(self, line):
        with self._log_lock:
            self._pending_log.append(str(line))

    def _camera_chosen(self, i):
        self._select_camera(i)

    def _select_camera(self, i):
        self.camera_combo.setCurrentIndex(i)
        index = self.camera_combo.itemData(i)
        self.status.setText("Opening webcam ...")
        QApplication.processEvents()
        if self.engine.open_camera(index):
            self._log(f"[+] Webcam {index} opened")
        self.settings.setValue("camera_index", index)

    def _ask_telemetry(self):
        box = QMessageBox(self)
        box.setWindowTitle("Hacker Cam")
        box.setIcon(QMessageBox.Question)
        box.setWindowFlag(Qt.WindowStaysOnTopHint)   # menu bar app: don't open behind others
        box.setText("Help improve Hacker Cam?")
        box.setInformativeText(
            "Share anonymous usage stats: which effects you use, the app version and your OS.\n\n"
            "Never your video, images, name, title or anything you type. "
            "You can change this any time in the window's Options.")
        yes = box.addButton("Share stats", QMessageBox.AcceptRole)
        box.addButton("No thanks", QMessageBox.RejectRole)
        box.exec()
        self.stats_check.setChecked(box.clickedButton() is yes)
        self.settings.setValue("telemetry", box.clickedButton() is yes)

    def _telemetry_toggled(self, on):
        if on and not self.stats.enabled:
            self.stats.set_enabled(True)
            self.stats.capture("telemetry_enabled")
        elif not on:
            self.stats.set_enabled(False)
        self.settings.setValue("telemetry", on)

    def _output_toggled(self, on):
        sending = self.engine.set_output(on)
        if on:
            self.stats.capture("virtual_camera_started", ok=sending)
        self.output_btn.setChecked(sending)
        self.settings.setValue("output", on)

    def _identity_changed(self):
        name = self.name_edit.text().strip() or "Anonymous"
        title = self.title_edit.text().strip()
        self.engine.call(lambda e: (setattr(e, "name", name), setattr(e, "title", title)))
        self.settings.setValue("name", name)
        self.settings.setValue("title", title)

    def _arm_entrance(self):
        self.engine.call(lambda e: e.entrance.arm())
        self.stats.capture("effect_used", effect="black_screen")
        self._log("[+] Black screen: press Entrance when ready")

    def _set_background(self, value):
        if self.engine.background != value:
            self.engine.call(lambda e: setattr(e, "background", value))
            self.stats.capture("effect_used", effect=value or "real_room")
            self._log(f"[+] Background: {value or 'real room'}")

    def _speed_changed(self, value):
        scale = value / 100
        self.engine.call(lambda e: setattr(e, "duration_scale", scale))
        self.settings.setValue("duration_scale", scale)

    def _hotkeys_toggled(self, on):
        if on and self.hotkeys is None:
            self.hotkeys = hi.start_hotkeys(self.engine.events)
            if self.hotkeys is None:
                self.hotkeys_check.setChecked(False)
                self._log("[!] Hotkeys unavailable. On macOS, allow Input Monitoring.")
        elif not on and self.hotkeys is not None:
            self.hotkeys.stop()
            self.hotkeys = None
        self.settings.setValue("hotkeys", self.hotkeys is not None)

    # --- refresh (UI thread, ~30x per second) ------------------------------

    @staticmethod
    def _sync(widget, checked):
        if widget.isChecked() != checked:
            widget.blockSignals(True)
            widget.setChecked(checked)
            widget.blockSignals(False)

    def _tick(self):
        if not self.engine.running:      # quit hotkey, or engine error
            self.quit_app()
            return
        frame = self.engine.latest_frame()
        if frame is not None and self.isVisible():   # no preview work while hidden
            self.preview.show_frame(frame)

        snap = self.engine.snapshot()
        self._sync(self.filter_btn, snap["filter"])
        self._sync(self.holo_btn, snap["hologram"])
        self._sync(self.away_btn, snap["away"])
        self._sync(self.output_btn, snap["output"])
        self._sync(self.bg_radios[snap["background"]], True)

        if snap["output"]:
            text = f"● LIVE → {snap['device']}   ·   {snap['fps']:.0f} fps"
            color = GREEN
        elif snap["output_error"]:
            text = ("○ Virtual camera unavailable. Install OBS Studio, click 'Start Virtual "
                    "Camera' once, stop it, then press 'Send to virtual camera'.")
            color = "#ffb347"
        else:
            text = f"○ Preview only (not sending to calls)   ·   {snap['fps']:.0f} fps"
            color = "#9fbf9f"
        if not snap["camera_ok"]:
            text += "   ·   webcam offline"
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color};")
        if self.tray is not None:
            self._sync_tray(snap, text)

        with self._log_lock:
            lines, self._pending_log = self._pending_log, []
        for line in lines:
            self.log_view.appendPlainText(line)

    @staticmethod
    def _sync_action(action, checked):
        # No blockSignals here: QActionGroup needs the signals to keep the
        # group exclusive, and our slots listen to triggered, not toggled.
        if action.isChecked() != checked:
            action.setChecked(checked)

    def _sync_tray(self, snap, status_text):
        self._sync_action(self.act_output, snap["output"])
        self._sync_action(self.act_away, snap["away"])
        self._sync_action(self.act_filter, snap["filter"])
        self._sync_action(self.act_holo, snap["hologram"])
        self._sync_action(self.act_bg[snap["background"]], True)
        cam = self.camera_combo.currentIndex()
        if 0 <= cam < len(self.act_cams):
            self._sync_action(self.act_cams[cam], True)
        short = status_text.split(". ")[0] if snap["output_error"] else status_text
        if self.menu_status.text() != short:
            self.menu_status.setText(short)
            self.tray.setToolTip(f"Hacker Cam\n{short}")
        if snap["output"] != self._tray_live:
            self._tray_live = snap["output"]
            self.tray.setIcon(self.icon_live if self._tray_live else self.icon_idle)

    def closeEvent(self, event):
        if self.tray is not None and not self._quitting:
            # Closing the window only hides it; the app keeps running in the tray.
            event.ignore()
            self.hide()
            if not self._told_about_tray:
                self._told_about_tray = True
                where = "menu bar" if sys.platform == "darwin" else "system tray"
                self.tray.showMessage("Hacker Cam", f"Still running in the {where}. "
                                      "Use its menu for effects, or Quit.",
                                      QSystemTrayIcon.Information, 4000)
            return
        self._shutdown()
        super().closeEvent(event)

    def _shutdown(self):
        if not self.timer.isActive() and not self.engine.running:
            return
        self.timer.stop()
        self.settings.setValue("filter", self.engine.filter_on)
        self.settings.setValue("hologram", self.engine.holo_on)
        self.settings.setValue("background", self.engine.background or "")
        if self.hotkeys is not None:
            self.hotkeys.stop()
        self.engine.stop()
        self.thread.join(timeout=2)
        self.engine.close()
        self.stats.capture("app_quit", minutes=self.session.minutes())
        self.stats.close()
        if self.tray is not None:
            self.tray.hide()


def self_test():
    """Exercise the parts that break when packaging (MediaPipe models and native
    library, OpenCV, Qt, virtual-camera and hotkey modules) without touching
    the webcam or the virtual camera. Exit code 0 = OK. Used by the build."""
    import importlib
    import tempfile
    import time
    import traceback
    if sys.stdout is None:   # windowed build on Windows: no console to print to
        sys.stdout = sys.stderr = open(
            os.path.join(tempfile.gettempdir(), "hackercam-selftest.txt"), "w", encoding="utf-8")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    e = None
    try:
        app = QApplication(sys.argv)
        make_icon(True)
        h, w = 720, 1280
        yy, xx = np.mgrid[0:h, 0:w]
        img = np.dstack([xx % 256, yy % 256, (xx + yy) % 256]).astype(np.uint8)

        class StubWebcam:
            ok = True
            def get(self): return img.copy()
            def close(self): pass

        e = hi.Engine(log=lambda *a: None)
        e.webcam = StubWebcam()
        steps = [("intro", lambda: e.command("replay")),
                 ("filter", lambda: e.command("filter")),
                 ("matrix", lambda: e.command("matrix")),
                 ("trace", lambda: e.command("trace")),
                 ("hologram", lambda: e.command("hologram")),
                 ("scan", lambda: e.command("scan")),
                 ("entrance", lambda: e.command("entrance")),
                 ("away", lambda: e.command("away"))]
        t = time.monotonic()
        for name, start in steps:
            start()
            for _ in range(15):
                t += 1 / 30
                e._handle_commands(t)
                frame = e.step(t)
                assert frame.shape == (h, w, 3), name
            print(f"  ok  {name}")
        assert e.vision.segment(img) is not None, "segmentation model failed"
        e.vision._get("face")
        assert "face" in e.vision._tasks, "face model failed"
        print("  ok  mediapipe models")
        for mod in ("pyvirtualcam", "pynput.keyboard", "PySide6.QtMultimedia"):
            importlib.import_module(mod)
            print(f"  ok  import {mod}")
        print(f"SELF-TEST OK (Hacker Cam {__version__})")
        return 0
    except Exception:
        traceback.print_exc()
        print("SELF-TEST FAILED")
        return 1
    finally:
        if e is not None:   # close MediaPipe before interpreter shutdown
            e.close()


def main():
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--version" in sys.argv:
        print(__version__)
        return
    app = QApplication(sys.argv)
    app.setApplicationName("Hacker Cam")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Menlo" if sys.platform == "darwin" else "Consolas", 12))
    app.setWindowIcon(make_icon(False))
    app.setQuitOnLastWindowClosed(False)        # keep running in the menu bar / tray
    win = MainWindow()
    if win.tray is None or "--window" in sys.argv or win.window_check.isChecked():
        win.show()
    else:
        where = "menu bar" if sys.platform == "darwin" else "system tray"
        win.tray.showMessage("Hacker Cam", f"Running in the {where}. Click the >_ icon for effects.",
                             QSystemTrayIcon.Information, 4000)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

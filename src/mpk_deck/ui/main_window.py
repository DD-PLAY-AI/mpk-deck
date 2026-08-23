import logging

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

from mpk_deck.config import (
    ACCENT_HEX,
    DEFAULT_ACTIONS_PATH,
    load_last_always_on_top,
    load_last_mode,
    load_last_theme,
    save_last_always_on_top,
    save_last_mode,
    save_last_theme,
)
from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import Binding, load_bindings, save_bindings
from mpk_deck.core.handlers import focus_window, launch_program, open_url, set_system_volume
from mpk_deck.midi.mpk_controller import MPKController
from mpk_deck.ui.action_config_dialog import ActionConfigDialog
from mpk_deck.ui.expanded_view import ExpandedView
from mpk_deck.ui.mini_view import MiniView

logger = logging.getLogger(__name__)


def build_action_engine() -> ActionEngine:
    engine = ActionEngine()
    engine.register_trigger("launch_program", launch_program)
    engine.register_trigger("open_url", open_url)
    engine.register_trigger("focus_window", focus_window)
    engine.register_continuous("set_system_volume", set_system_volume)
    try:
        bindings = load_bindings(DEFAULT_ACTIONS_PATH)
    except Exception:
        logger.exception("failed to load %s, starting with no bindings", DEFAULT_ACTIONS_PATH)
        bindings = []
    engine.load_bindings(bindings)
    return engine


def _tray_icon() -> QIcon:
    """A small rounded square with a 2x2 pad grid glyph, drawn in the app's accent color."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT_HEX))
    painter.drawRoundedRect(QRectF(1, 1, 30, 30), 8, 8)
    painter.setBrush(QColor(255, 255, 255, 230))
    for row in range(2):
        for col in range(2):
            painter.drawRoundedRect(QRectF(7 + col * 11, 7 + row * 11, 8, 8), 2, 2)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Personal Deck")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._engine = build_action_engine()
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False

        self._midi = MPKController(self._engine)
        self._midi_detected = self._midi.start()

        self._mini_view = MiniView()
        self._mini_view.pad_activated.connect(self._on_control_activated)
        self._mini_view.pad_configure_requested.connect(self._on_control_configure_requested)
        self._mini_view.update_bindings(self._bindings)
        self._expanded_view = ExpandedView()
        self._expanded_view.control_clicked.connect(self._on_control_configure_requested)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._mini_view)
        layout.addWidget(self._expanded_view)
        self.setCentralWidget(container)

        self._mode = load_last_mode()
        self._theme = load_last_theme()
        self._always_on_top = load_last_always_on_top()
        self._apply_mode()
        self._apply_theme()
        self._apply_always_on_top()

        self._tray = self._build_tray()

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(_tray_icon(), self)
        tray.setToolTip("Personal Deck" if self._midi_detected else "Personal Deck (MPK not detected)")

        menu = QMenu()
        toggle_mode_action = menu.addAction("Toggle Mini/Expanded")
        toggle_mode_action.triggered.connect(self._toggle_mode)

        menu.addSeparator()
        light_action = menu.addAction("Light Mode")
        light_action.setCheckable(True)
        dark_action = menu.addAction("Dark Mode")
        dark_action.setCheckable(True)
        light_action.triggered.connect(lambda: self._set_theme("light"))
        dark_action.triggered.connect(lambda: self._set_theme("dark"))
        self._light_action = light_action
        self._dark_action = dark_action
        self._sync_theme_menu()

        menu.addSeparator()
        always_on_top_action = menu.addAction("Always on Top")
        always_on_top_action.setCheckable(True)
        always_on_top_action.setChecked(self._always_on_top)
        always_on_top_action.triggered.connect(self._toggle_always_on_top)
        self._always_on_top_action = always_on_top_action

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        self._menu = menu
        tray.setContextMenu(menu)
        tray.show()
        return tray

    def _sync_theme_menu(self) -> None:
        self._light_action.setChecked(self._theme == "light")
        self._dark_action.setChecked(self._theme == "dark")

    def _apply_mode(self) -> None:
        self._mini_view.setVisible(self._mode == "mini")
        self._expanded_view.setVisible(self._mode == "expanded")
        self._enforce_aspect()

    def _enforce_aspect(self) -> None:
        """Safety net on top of WindowGripMixin's live aspect-locked resize math —
        catches any drift from window-manager-driven moves (e.g. OS snap)."""
        if self._resizing_guard:
            return
        aspect = self._mini_view.locked_aspect if self._mode == "mini" else self._expanded_view.locked_aspect
        target_h = round(self.width() / aspect)
        if abs(self.height() - target_h) > 1:
            self._resizing_guard = True
            self.resize(self.width(), target_h)
            self._resizing_guard = False

    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)

    def _toggle_mode(self) -> None:
        self._mode = "expanded" if self._mode == "mini" else "mini"
        save_last_mode(self._mode)
        self._apply_mode()

    def _set_theme(self, theme: str) -> None:
        self._theme = theme
        save_last_theme(theme)
        self._apply_theme()
        self._sync_theme_menu()

    def _apply_always_on_top(self) -> None:
        flags = self.windowFlags()
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def _toggle_always_on_top(self) -> None:
        self._always_on_top = not self._always_on_top
        save_last_always_on_top(self._always_on_top)
        self._apply_always_on_top()

    def _on_control_activated(self, control: str) -> None:
        self._engine.trigger(control)

    def _on_control_configure_requested(self, control: str) -> None:
        existing = self._bindings.get(control)
        dialog = ActionConfigDialog(control, existing, parent=self)
        if dialog.exec():
            binding = dialog.result_binding()
            self._bindings[control] = binding
            self._engine.load_bindings(list(self._bindings.values()))
            save_bindings(DEFAULT_ACTIONS_PATH, list(self._bindings.values()))
            self._mini_view.update_bindings(self._bindings)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._enforce_aspect()

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._midi.stop()
        super().closeEvent(event)

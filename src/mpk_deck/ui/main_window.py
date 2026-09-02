import logging

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QMenu, QSystemTrayIcon, QVBoxLayout, QWidget

from mpk_deck.config import (
    ACCENT_HEX,
    DEFAULT_ACTIONS_PATH,
    load_last_accent,
    load_last_always_on_top,
    load_last_knob_style,
    load_last_mode,
    load_last_theme,
    save_last_accent,
    save_last_always_on_top,
    save_last_knob_style,
    save_last_mode,
    save_last_theme,
)
from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.core.action_registry import (
    Bank,
    Binding,
    DeckConfig,
    default_joystick_bindings,
    generate_bank_id,
    load_config,
    save_config,
)
from mpk_deck.core.handlers import focus_window, launch_program, open_url, scroll_horizontal, scroll_vertical, set_system_volume
from mpk_deck.midi.mpk_controller import MPKController
from mpk_deck.ui.accent import ACCENT_CHOICES
from mpk_deck.ui.action_config_dialog import ActionConfigDialog
from mpk_deck.ui.bank_indicator import BankIndicator
from mpk_deck.ui.bank_hint import BankHint
from mpk_deck.ui.expanded_view import ExpandedView
from mpk_deck.ui.midi_status_dot import MidiStatusDot
from mpk_deck.ui.mini_view import MiniView

logger = logging.getLogger(__name__)

MIDI_POLL_INTERVAL_MS = 3000
STATUS_DOT_MARGIN = 10
MINI_DEFAULT_WIDTH = 320  # launch compact in mini mode - roughly the expanded view's pad cluster
EXPANDED_DEFAULT_WIDTH = 680
JOYSTICK_TIMER_INTERVAL_MS = 50  # 20Hz repeat-while-held; only runs while deflected


def build_action_engine(config: DeckConfig, on_bank_changed, on_continuous, on_trigger) -> ActionEngine:
    engine = ActionEngine(on_bank_changed=on_bank_changed, on_continuous=on_continuous, on_trigger=on_trigger)
    engine.register_trigger("launch_program", launch_program)
    engine.register_trigger("open_url", open_url)
    engine.register_trigger("focus_window", focus_window)
    engine.register_continuous("set_system_volume", set_system_volume)
    engine.register_continuous("scroll_horizontal", scroll_horizontal)
    engine.register_continuous("scroll_vertical", scroll_vertical)
    engine.load_banks(
        {bank_id: bank.bindings for bank_id, bank in config.banks.items()},
        config.switch_bindings,
        config.active_bank,
    )
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


def _accent_icon(hex_color: str) -> QIcon:
    """A small solid-color circle, shown next to each accent choice in the Design menu."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(hex_color))
    painter.drawEllipse(1, 1, 14, 14)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Personal Deck")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._config = load_config(DEFAULT_ACTIONS_PATH)
        self._bank_names: dict[str, str] = {bank_id: bank.name for bank_id, bank in self._config.banks.items()}
        self._joystick_values: dict[str, float] = {"joystick_x": 0.0, "joystick_y": 0.0}
        self._engine = build_action_engine(
            self._config, self._on_bank_changed, self._on_joystick_continuous, self._on_trigger
        )
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)
        self._resizing_guard = False
        self._accent_hex = load_last_accent()
        self._knob_style = load_last_knob_style()

        self._joystick_timer = QTimer(self)
        self._joystick_timer.timeout.connect(self._on_joystick_timer_tick)

        self._midi = MPKController(
            self._engine,
            on_bank_b_pad=self._on_bank_b_pad,
            dispatch=lambda fn: QTimer.singleShot(0, self, fn),  # run engine calls on the GUI thread
        )
        self._midi_detected = self._midi.start()

        self._midi_status_dot = MidiStatusDot(self)
        self._midi_status_dot.set_connected(self._midi_detected)
        self._midi_status_dot.retry_requested.connect(self._poll_midi)
        self._midi_timer = QTimer(self)
        self._midi_timer.timeout.connect(self._poll_midi)
        self._midi_timer.start(MIDI_POLL_INTERVAL_MS)

        self._bank_indicator = BankIndicator(self)
        self._bank_indicator.set_bank_name(self._bank_names.get(self._engine.active_bank, self._engine.active_bank))
        self._bank_hint = BankHint(self)
        self._bank_hint.set_accent(self._accent_hex)

        self._mini_view = MiniView()
        self._mini_view.pad_activated.connect(self._on_control_activated)
        self._mini_view.pad_configure_requested.connect(self._on_control_configure_requested)
        self._mini_view.update_bindings(self._bindings, self._bank_names)
        self._expanded_view = ExpandedView()
        self._expanded_view.control_activated.connect(self._on_control_activated)
        self._expanded_view.control_configure_requested.connect(self._on_control_configure_requested)
        self._expanded_view.decorative_button_activated.connect(self._on_decorative_button)
        self._expanded_view.update_bindings(self._bindings, self._bank_names)

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
        self._apply_design()
        self._mode_widths = {"mini": MINI_DEFAULT_WIDTH, "expanded": EXPANDED_DEFAULT_WIDTH}
        QTimer.singleShot(0, self._resize_for_mode)

        self._tray = self._build_tray()
        self._position_overlay_widgets()

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
        design_menu = menu.addMenu("Design")
        knob_style_group = QActionGroup(design_menu)
        for style, label in [("A", "Knob: Number + Tick"), ("B", "Knob: Needle")]:
            action = design_menu.addAction(label)
            action.setCheckable(True)
            action.setActionGroup(knob_style_group)
            action.setChecked(style == self._knob_style)
            action.triggered.connect(lambda checked, s=style: self._set_knob_style(s))
        design_menu.addSeparator()
        accent_group = QActionGroup(design_menu)
        for name, hex_color in ACCENT_CHOICES:
            action = design_menu.addAction(_accent_icon(hex_color), name.capitalize())
            action.setCheckable(True)
            action.setActionGroup(accent_group)
            action.setChecked(hex_color == self._accent_hex)
            action.triggered.connect(lambda checked, h=hex_color: self._set_accent(h))

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

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

    def _resize_for_mode(self) -> None:
        """Each mode keeps its own window width (default until the user resizes it),
        so toggling mini<->expanded snaps back to a sensible size instead of carrying
        the other mode's width over. Deferred so the just-toggled view visibility has
        settled the layout's minimum size first - otherwise mini can't shrink past
        ExpandedView's minimum width."""
        active = self._mini_view if self._mode == "mini" else self._expanded_view
        width = self._mode_widths[self._mode]
        self.resize(width, round(width / active.locked_aspect))

    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        self._mini_view.set_dark(dark)
        self._expanded_view.set_dark(dark)

    def _apply_design(self) -> None:
        self._mini_view.set_accent(self._accent_hex)
        self._expanded_view.set_accent(self._accent_hex)
        self._expanded_view.set_knob_style(self._knob_style)
        self._bank_indicator.set_accent(self._accent_hex)
        self._bank_hint.set_accent(self._accent_hex)

    def _set_accent(self, accent_hex: str) -> None:
        self._accent_hex = accent_hex
        save_last_accent(accent_hex)
        self._apply_design()

    def _set_knob_style(self, style: str) -> None:
        self._knob_style = style
        save_last_knob_style(style)
        self._apply_design()

    def _toggle_mode(self) -> None:
        self._mode_widths[self._mode] = self.width()
        self._mode = "expanded" if self._mode == "mini" else "mini"
        save_last_mode(self._mode)
        self._apply_mode()
        QTimer.singleShot(0, self._resize_for_mode)

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

    def _position_overlay_widgets(self) -> None:
        dot = self._midi_status_dot
        dot.move(self.width() - dot.width() - STATUS_DOT_MARGIN, self.height() - dot.height() - STATUS_DOT_MARGIN)
        dot.raise_()
        indicator = self._bank_indicator
        indicator.move(dot.x() - indicator.width() - STATUS_DOT_MARGIN, dot.y() + (dot.height() - indicator.height()) // 2)
        indicator.raise_()
        hint = self._bank_hint
        hint.move((self.width() - hint.width()) // 2, STATUS_DOT_MARGIN)
        hint.raise_()

    def _poll_midi(self) -> None:
        was_detected = self._midi_detected
        self._midi_detected = self._midi.poll_connection()
        if self._midi_detected != was_detected:
            logger.info("MIDI %s", "connected" if self._midi_detected else "disconnected")
        self._midi_status_dot.set_connected(self._midi_detected)
        self._tray.setToolTip("Personal Deck" if self._midi_detected else "Personal Deck (MPK not detected)")

    def _on_control_activated(self, control: str) -> None:
        self._engine.trigger(control)

    def _on_trigger(self, control: str, ok: bool) -> None:
        # `ok` (handler success/failure) is ignored - the flash is just press feedback,
        # the same accent glow a mouse click gives.
        QTimer.singleShot(0, self, lambda: self._apply_trigger_flash(control))

    def _apply_trigger_flash(self, control: str) -> None:
        view = self._mini_view if self._mode == "mini" else self._expanded_view
        view.flash_control(control)

    def _on_bank_b_pad(self) -> None:
        QTimer.singleShot(0, self, self._show_bank_hint)

    def _show_bank_hint(self) -> None:
        self._bank_hint.show_hint()
        self._position_overlay_widgets()

    def _on_decorative_button(self, control: str) -> None:
        QMessageBox.information(
            self, "설정 불가",
            "이 버튼은 MIDI를 전송하지 않아 기능을 설정할 수 없습니다.",
        )

    def _on_bank_changed(self, bank_id: str) -> None:
        QTimer.singleShot(0, self, lambda: self._apply_bank_change(bank_id))

    def _apply_bank_change(self, bank_id: str) -> None:
        self._bindings = dict(self._engine.bindings)
        self._mini_view.update_bindings(self._bindings, self._bank_names)
        self._expanded_view.update_bindings(self._bindings, self._bank_names)
        self._bank_indicator.set_bank_name(self._bank_names.get(bank_id, bank_id))
        self._position_overlay_widgets()
        self._config.active_bank = bank_id
        save_config(DEFAULT_ACTIONS_PATH, self._config)

    def _on_joystick_continuous(self, control: str, value: float) -> None:
        QTimer.singleShot(0, self, lambda: self._apply_joystick_continuous(control, value))

    def _apply_joystick_continuous(self, control: str, value: float) -> None:
        if control in self._joystick_values:
            self._joystick_values[control] = value
            # Negate Y for the widget: hardware "push up" sends a rising value, and
            # the joystick handle should move up (screen -y) to match.
            self._expanded_view.set_joystick_deflection(
                self._joystick_values["joystick_x"], -self._joystick_values["joystick_y"]
            )
            any_active = any(v != 0.0 for v in self._joystick_values.values())
            if any_active and not self._joystick_timer.isActive():
                self._joystick_timer.start(JOYSTICK_TIMER_INTERVAL_MS)
            elif not any_active and self._joystick_timer.isActive():
                self._joystick_timer.stop()
        elif control.startswith("knob_"):
            self._expanded_view.set_knob_value(control, value)

    def _on_joystick_timer_tick(self) -> None:
        for control, value in self._joystick_values.items():
            if value != 0.0:
                self._engine.set_continuous(control, value)

    def _on_control_configure_requested(self, control: str) -> None:
        existing = self._bindings.get(control)
        dialog = ActionConfigDialog(
            control, existing, parent=self, bank_names=self._bank_names,
            accent_hex=self._accent_hex, dark=self._theme == "dark",
        )
        if not dialog.exec():
            return
        if control in self._config.switch_bindings:
            self._save_bank_binding(control, dialog.result_bank_name())
            return
        binding = dialog.result_binding()
        if binding.action == "switch_bank":
            self._save_bank_binding(control, dialog.result_bank_name())
        else:
            self._save_normal_binding(control, binding)

    def _save_bank_binding(self, control: str, bank_name: str) -> None:
        bank_name = bank_name or "New Bank"
        if control in self._config.switch_bindings:
            bank_id = self._config.switch_bindings[control]
            self._config.banks[bank_id].name = bank_name
        else:
            bank_id = generate_bank_id(bank_name, self._config.banks.keys())
            self._config.banks[bank_id] = Bank(name=bank_name, bindings=default_joystick_bindings())
            self._config.switch_bindings[control] = bank_id
        self._bank_names[bank_id] = bank_name
        binding = Binding(control=control, type="trigger", action="switch_bank", params={"bank_id": bank_id})
        self._bindings[control] = binding
        self._sync_after_binding_change()
        if bank_id == self._engine.active_bank:
            self._bank_indicator.set_bank_name(bank_name)

    def _save_normal_binding(self, control: str, binding: Binding) -> None:
        active_id = self._engine.active_bank
        bank = self._config.banks[active_id]
        bank.bindings = [b for b in bank.bindings if b.control != control] + [binding]
        self._bindings[control] = binding
        self._sync_after_binding_change()

    def _sync_after_binding_change(self) -> None:
        self._engine.load_banks(
            {bank_id: bank.bindings for bank_id, bank in self._config.banks.items()},
            self._config.switch_bindings,
            self._engine.active_bank,
        )
        self._bindings = dict(self._engine.bindings)
        save_config(DEFAULT_ACTIONS_PATH, self._config)
        self._mini_view.update_bindings(self._bindings, self._bank_names)
        self._expanded_view.update_bindings(self._bindings, self._bank_names)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._enforce_aspect()
        self._position_overlay_widgets()

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._menu.exec(event.globalPos())

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._midi.stop()
        super().closeEvent(event)

    def _quit(self) -> None:
        """Qt.WindowType.Tool windows don't trigger quitOnLastWindowClosed, so close()
        alone would hide the window forever without ever ending the process."""
        self.close()
        QApplication.instance().quit()

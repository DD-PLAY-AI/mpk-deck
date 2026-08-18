import logging

from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget

from mpk_deck.config import DEFAULT_ACTIONS_PATH, load_last_mode, save_last_mode
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Personal Deck")

        self._engine = build_action_engine()
        self._bindings: dict[str, Binding] = dict(self._engine.bindings)

        self._midi = MPKController(self._engine)
        if not self._midi.start():
            self.setWindowTitle("Personal Deck (MPK not detected)")

        self._mini_view = MiniView()
        self._mini_view.pad_clicked.connect(self._on_control_clicked)
        self._expanded_view = ExpandedView()
        self._expanded_view.control_clicked.connect(self._on_control_clicked)

        toggle = QPushButton("Toggle Mini/Expanded")
        toggle.clicked.connect(self._toggle_mode)

        container = QWidget(self)
        container.setStyleSheet("background-color: #23242b;")
        layout = QVBoxLayout(container)
        layout.addWidget(toggle)
        layout.addWidget(self._mini_view)
        layout.addWidget(self._expanded_view)
        self.setCentralWidget(container)

        self._mode = load_last_mode()
        self._apply_mode()

    def _apply_mode(self) -> None:
        self._mini_view.setVisible(self._mode == "mini")
        self._expanded_view.setVisible(self._mode == "expanded")

    def _toggle_mode(self) -> None:
        self._mode = "expanded" if self._mode == "mini" else "mini"
        save_last_mode(self._mode)
        self._apply_mode()

    def _on_control_clicked(self, control: str) -> None:
        existing = self._bindings.get(control)
        dialog = ActionConfigDialog(control, existing, parent=self)
        if dialog.exec():
            binding = dialog.result_binding()
            self._bindings[control] = binding
            self._engine.load_bindings(list(self._bindings.values()))
            save_bindings(DEFAULT_ACTIONS_PATH, list(self._bindings.values()))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._midi.stop()
        super().closeEvent(event)

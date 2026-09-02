import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from mpk_deck.ui.main_window import MainWindow


def test_midi_callbacks_reach_gui_thread(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("mpk_deck.ui.main_window.MPKController.start", lambda self: False)
    window = MainWindow()
    window._mode = "mini"
    window._apply_mode()

    worker = threading.Thread(
        target=lambda: (
            window._on_trigger("pad_1", True),
            window._on_joystick_continuous("joystick_y", 1.0),
        )
    )
    worker.start()
    worker.join()

    for _ in range(10):
        app.processEvents()

    assert window._mini_view._pads["pad_1"]._glow.isEnabled()
    # Y is negated for the widget: "push up" (value 1.0) moves the handle up (screen -y).
    assert window._expanded_view._joystick._y == -1.0
    assert window._expanded_view._knobs["knob_1"]._value == 0.0
    window.close()

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from mpk_deck.ui.expanded_view import KnobWidget


class _WheelEvent:
    def __init__(self, delta_y: int) -> None:
        self._delta_y = delta_y
        self.accepted = False

    def angleDelta(self) -> QPoint:  # noqa: N802 (Qt API)
        return QPoint(0, self._delta_y)

    def accept(self) -> None:
        self.accepted = True


def test_apply_wheel_notches_accumulates_and_clamps() -> None:
    assert KnobWidget._apply_wheel_notches(0.5, 2) == 0.6
    assert KnobWidget._apply_wheel_notches(0.98, 1) == 1.0
    assert KnobWidget._apply_wheel_notches(0.02, -1) == 0.0


def test_wheel_event_updates_knob_and_emits_clamped_value() -> None:
    QApplication.instance() or QApplication([])
    knob = KnobWidget("1")
    values: list[float] = []
    knob.value_scrolled.connect(values.append)
    event = _WheelEvent(360)

    knob.set_value(0.9)
    knob.wheelEvent(event)

    assert knob._value == 1.0
    assert values == [1.0]
    assert event.accepted


def test_wheel_event_routes_knob_value_to_main_window_engine(monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    monkeypatch.setattr("mpk_deck.ui.main_window.MPKController.start", lambda self: False)
    from mpk_deck.ui.main_window import MainWindow

    window = MainWindow()
    received: list[tuple[str, float]] = []
    monkeypatch.setattr(window._engine, "set_continuous", lambda control, value: received.append((control, value)))

    window._expanded_view._knobs["knob_2"].wheelEvent(_WheelEvent(120))

    assert received == [("knob_2", 0.05)]
    window.close()

import mido
import pytest

from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.midi import mpk_controller
from mpk_deck.midi.mpk_controller import MPKController


@pytest.fixture(autouse=True)
def _clear_abandoned_ports():
    mpk_controller._ABANDONED_PORTS.clear()
    yield
    mpk_controller._ABANDONED_PORTS.clear()


def test_find_port_name_matches_substring(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Foo", "MPK mini mk II 1"])
    controller = MPKController(action_engine=ActionEngine())
    assert controller.find_port_name() == "MPK mini mk II 1"


def test_find_port_name_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Foo"])
    controller = MPKController(action_engine=ActionEngine())
    assert controller.find_port_name() is None


def test_on_message_triggers_engine_for_pad():
    engine = ActionEngine()
    calls = []
    engine.trigger = lambda control: calls.append(control)
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("note_on", note=36, velocity=100))

    assert calls == ["pad_1"]


def test_on_message_sets_continuous_for_knob():
    engine = ActionEngine()
    calls = []
    engine.set_continuous = lambda control, value: calls.append((control, value))
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("control_change", control=2, value=64))

    assert calls == [("knob_2", 64 / 127.0)]


def test_on_message_ignores_unmapped_message():
    engine = ActionEngine()
    calls = []
    engine.trigger = lambda control: calls.append(control)
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("note_off", note=36))

    assert calls == []


def test_on_message_fires_bank_b_pad_callback_for_note_44():
    calls = []
    controller = MPKController(action_engine=ActionEngine(), on_bank_b_pad=lambda: calls.append(True))

    controller._on_message(mido.Message("note_on", note=44, velocity=100))

    assert calls == [True]


def test_on_message_does_not_fire_bank_b_pad_callback_for_keybed_note():
    calls = []
    controller = MPKController(action_engine=ActionEngine(), on_bank_b_pad=lambda: calls.append(True))

    controller._on_message(mido.Message("note_on", note=48, velocity=100))

    assert calls == []


def test_on_message_without_bank_b_callback_does_not_raise():
    controller = MPKController(action_engine=ActionEngine())
    controller._on_message(mido.Message("note_on", note=44, velocity=100))  # must not raise


class _FakePort:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeRtMidiIn:
    def __init__(self) -> None:
        self.error_callback = None

    def set_error_callback(self, callback) -> None:
        self.error_callback = callback


class _FakeRtMidiPort(_FakePort):
    def __init__(self) -> None:
        super().__init__()
        self._rt = _FakeRtMidiIn()


class _RaisingErrorCallbackRtMidiIn:
    def set_error_callback(self, callback) -> None:
        raise RuntimeError("unsupported")


class _RaisingErrorCallbackPort(_FakePort):
    def __init__(self) -> None:
        super().__init__()
        self._rt = _RaisingErrorCallbackRtMidiIn()


def test_start_installs_non_raising_rtmidi_error_callback(monkeypatch, caplog):
    port = _FakeRtMidiPort()
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    monkeypatch.setattr(mido, "open_input", lambda name, callback: port)
    controller = MPKController(action_engine=ActionEngine())

    assert controller.start() is True
    assert port._rt.error_callback is not None

    port._rt.error_callback(7, "device removed", None)  # must not raise

    assert "device removed" in caplog.text


def test_start_survives_error_callback_install_failure(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    monkeypatch.setattr(
        mido, "open_input", lambda name, callback: _RaisingErrorCallbackPort()
    )
    controller = MPKController(action_engine=ActionEngine())

    assert controller.start() is True


def test_on_message_swallows_translate_error(monkeypatch, caplog):
    def raise_from_translate(message):
        raise RuntimeError("translate failed")

    monkeypatch.setattr(mpk_controller, "translate", raise_from_translate)
    controller = MPKController(action_engine=ActionEngine())

    controller._on_message(mido.Message("note_on", note=36, velocity=100))  # must not raise

    assert "error handling MIDI input callback" in caplog.text
    assert "translate failed" in caplog.text


def test_on_message_swallows_engine_error(caplog):
    engine = ActionEngine()
    engine.trigger = lambda control: (_ for _ in ()).throw(RuntimeError("handler failed"))
    controller = MPKController(action_engine=engine)

    controller._on_message(mido.Message("note_on", note=36, velocity=100))  # must not raise

    assert "error handling MIDI input callback" in caplog.text
    assert "handler failed" in caplog.text


def test_poll_connection_connects_when_device_appears(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    opened = []
    monkeypatch.setattr(mido, "open_input", lambda name, callback: opened.append(name) or _FakePort())
    controller = MPKController(action_engine=ActionEngine())

    assert controller.poll_connection() is True
    assert opened == ["MPK mini mk II 1"]


def test_poll_connection_stays_disconnected_when_device_absent(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["Foo"])
    monkeypatch.setattr(mido, "open_input", lambda name, callback: (_ for _ in ()).throw(AssertionError("should not open")))
    controller = MPKController(action_engine=ActionEngine())

    assert controller.poll_connection() is False


def test_poll_connection_stays_connected_without_reopening(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    open_count = []
    monkeypatch.setattr(mido, "open_input", lambda name, callback: open_count.append(1) or _FakePort())
    controller = MPKController(action_engine=ActionEngine())
    controller.poll_connection()

    assert controller.poll_connection() is True
    assert len(open_count) == 1


def test_poll_connection_abandons_vanished_port_without_closing_it(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    monkeypatch.setattr(mido, "open_input", lambda name, callback: _FakePort())
    controller = MPKController(action_engine=ActionEngine())
    controller.poll_connection()
    port = controller._port

    monkeypatch.setattr(mido, "get_input_names", lambda: [])
    assert controller.poll_connection() is False
    assert controller._port is None
    # closing a vanished rtmidi WinMM port crashes the process, so it must NOT be closed
    assert port.closed is False
    assert port in mpk_controller._ABANDONED_PORTS


class _RaisingClosePort:
    """Mimics rtmidi crashing/raising from close() when the device is already gone."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        raise RuntimeError("MidiInWinMM::openPort: error closing Windows MM MIDI input port")


def test_stop_does_not_close_a_port_whose_device_is_gone(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: [])
    controller = MPKController(action_engine=ActionEngine())
    port = _RaisingClosePort()
    controller._port = port

    controller.stop()  # must not raise, must not call close()

    assert controller._port is None
    assert port in mpk_controller._ABANDONED_PORTS


def test_stop_closes_the_port_normally_when_device_is_still_present(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    controller = MPKController(action_engine=ActionEngine())
    port = _FakePort()
    controller._port = port

    controller.stop()

    assert port.closed is True
    assert controller._port is None
    assert port not in mpk_controller._ABANDONED_PORTS


def test_poll_connection_survives_disconnect_when_close_would_raise(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    monkeypatch.setattr(mido, "open_input", lambda name, callback: _RaisingClosePort())
    controller = MPKController(action_engine=ActionEngine())
    controller.poll_connection()

    monkeypatch.setattr(mido, "get_input_names", lambda: [])
    assert controller.poll_connection() is False  # must not raise (close() never called)
    assert controller._port is None


def test_start_returns_false_when_open_input_raises(monkeypatch):
    monkeypatch.setattr(mido, "get_input_names", lambda: ["MPK mini mk II 1"])
    monkeypatch.setattr(
        mido, "open_input", lambda name, callback: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    controller = MPKController(action_engine=ActionEngine())

    assert controller.start(log=False) is False
    assert controller._port is None

from mpk_deck.core import handlers


def test_launch_program_calls_popen_with_path(monkeypatch):
    calls = []
    monkeypatch.setattr(handlers.subprocess, "Popen", lambda args, **kw: calls.append(args))
    handlers.launch_program({"path": "C:/x.exe"})
    assert calls == [["C:/x.exe"]]


def test_launch_program_missing_path_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(handlers.subprocess, "Popen", lambda args, **kw: calls.append(args))
    handlers.launch_program({})
    assert calls == []


def test_open_url_calls_webbrowser_open(monkeypatch):
    calls = []
    monkeypatch.setattr(handlers.webbrowser, "open", lambda url: calls.append(url))
    handlers.open_url({"url": "https://example.com"})
    assert calls == ["https://example.com"]


def test_open_url_missing_url_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(handlers.webbrowser, "open", lambda url: calls.append(url))
    handlers.open_url({})
    assert calls == []


def test_focus_window_calls_finder_with_title():
    calls = []
    handlers.focus_window({"title_contains": "Notepad"}, finder=lambda title: calls.append(title))
    assert calls == ["Notepad"]


def test_focus_window_missing_param_does_not_call_finder():
    calls = []
    handlers.focus_window({}, finder=lambda title: calls.append(title))
    assert calls == []


def test_set_system_volume_calls_setter_with_clamped_value():
    calls = []
    handlers.set_system_volume({}, 1.5, volume_setter=calls.append)
    assert calls == [1.0]


def test_set_system_volume_clamps_negative_value():
    calls = []
    handlers.set_system_volume({}, -0.2, volume_setter=calls.append)
    assert calls == [0.0]


def test_set_system_volume_passes_through_valid_value():
    calls = []
    handlers.set_system_volume({}, 0.42, volume_setter=calls.append)
    assert calls == [0.42]


def test_set_display_brightness_converts_normalized_value_to_percent(monkeypatch):
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 0.5, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, 0.0, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, 1.0, brightness_setter=calls.append, now=0.0)
    assert calls == [50, 0, 100]


def test_set_display_brightness_clamps_out_of_range(monkeypatch):
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 1.7, brightness_setter=calls.append, now=0.0)
    handlers._LAST_APPLIED.clear()
    handlers.set_display_brightness({}, -0.3, brightness_setter=calls.append, now=0.0)
    assert calls == [100, 0]


def test_set_display_brightness_throttles_rapid_calls():
    handlers._LAST_APPLIED.clear()
    calls = []
    handlers.set_display_brightness({}, 0.1, brightness_setter=calls.append, now=0.00)
    handlers.set_display_brightness({}, 0.2, brightness_setter=calls.append, now=0.05)  # dropped
    handlers.set_display_brightness({}, 0.3, brightness_setter=calls.append, now=0.20)  # applied
    assert calls == [10, 30]


def test_scroll_notches_scales_linearly_with_sensitivity():
    assert handlers._scroll_notches(1.0, 1.0) == 3
    assert handlers._scroll_notches(1.0, 2.0) == 6


def test_scroll_notches_negative_value_gives_negative_notches():
    assert handlers._scroll_notches(-1.0, 1.0) == -3


def test_scroll_notches_small_deflection_gives_fewer_notches():
    assert handlers._scroll_notches(0.1, 1.0) == 0
    assert handlers._scroll_notches(0.5, 1.0) == round(0.5 * 3)


def test_scroll_notches_clamps_out_of_range_value():
    assert handlers._scroll_notches(5.0, 1.0) == 3
    assert handlers._scroll_notches(-5.0, 1.0) == -3


def test_scroll_horizontal_calls_sender_with_horizontal_true():
    calls = []
    handlers.scroll_horizontal({"sensitivity": 1.0}, 1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": True, "notches": 3}]


def test_scroll_vertical_calls_sender_with_horizontal_false():
    calls = []
    handlers.scroll_vertical({"sensitivity": 1.0}, -1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": False, "notches": -3}]


def test_scroll_horizontal_zero_deflection_does_not_call_sender():
    calls = []
    handlers.scroll_horizontal({"sensitivity": 1.0}, 0.0, sender=lambda **kw: calls.append(kw))
    assert calls == []


def test_scroll_horizontal_missing_sensitivity_defaults_to_one():
    calls = []
    handlers.scroll_horizontal({}, 1.0, sender=lambda **kw: calls.append(kw))
    assert calls == [{"horizontal": True, "notches": 3}]


def test_apply_layout_restores_the_named_layout():
    from mpk_deck.core.handlers import apply_layout
    from mpk_deck.core.layout_store import Layout

    layout = Layout(name="L", items=[])
    got = []
    apply_layout({"layout_id": "abc"}, loader=lambda: {"abc": layout}, restore=lambda lo: got.append(lo))
    assert got == [layout]


def test_apply_layout_no_id_is_a_noop():
    from mpk_deck.core.handlers import apply_layout

    called = []
    apply_layout({}, loader=lambda: {}, restore=lambda lo: called.append(lo))
    assert called == []


def test_apply_layout_unknown_id_is_a_noop(caplog):
    from mpk_deck.core.handlers import apply_layout

    called = []
    apply_layout({"layout_id": "missing"}, loader=lambda: {}, restore=lambda lo: called.append(lo))
    assert called == []
    assert "not found" in caplog.text.lower()

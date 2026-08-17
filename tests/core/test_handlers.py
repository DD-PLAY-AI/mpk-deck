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

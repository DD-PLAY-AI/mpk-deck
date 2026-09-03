from types import SimpleNamespace

from mpk_deck.core.nl_action import parse_nl_action
from mpk_deck.core.program_finder import InstalledProgram

PROGRAMS = [
    InstalledProgram(name="KakaoTalk", path="C:/Program Files (x86)/Kakao/KakaoTalk/KakaoTalk.exe"),
    InstalledProgram(name="Chrome", path="C:/Program Files/Google/Chrome/Application/chrome.exe"),
]


class FakeMessages:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._exc:
            raise self._exc
        return self._response


class FakeClient:
    def __init__(self, response=None, exc=None):
        self.messages = FakeMessages(response, exc)


def _tool_use_response(input_dict):
    block = SimpleNamespace(type="tool_use", name="propose_binding", input=input_dict)
    return SimpleNamespace(content=[block])


def test_launch_program_matches_installed_program():
    client = FakeClient(_tool_use_response({"action": "launch_program", "program_name": "KakaoTalk"}))

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS, client=client)

    assert result.action == "launch_program"
    assert result.type == "trigger"
    assert result.params == {"path": "C:/Program Files (x86)/Kakao/KakaoTalk/KakaoTalk.exe"}


def test_launch_program_rejects_program_not_in_installed_list():
    client = FakeClient(_tool_use_response({"action": "launch_program", "program_name": "Some Fake App"}))

    result = parse_nl_action("가짜 앱 열어줘", PROGRAMS, client=client)

    assert result is None


def test_open_url_adds_https_scheme_when_missing():
    client = FakeClient(_tool_use_response({"action": "open_url", "url": "youtube.com"}))

    result = parse_nl_action("유튜브 열어줘", PROGRAMS, client=client)

    assert result.action == "open_url"
    assert result.params == {"url": "https://youtube.com"}


def test_focus_window_passes_through_title():
    client = FakeClient(_tool_use_response({"action": "focus_window", "title_contains": "Notepad"}))

    result = parse_nl_action("메모장 찾아줘", PROGRAMS, client=client)

    assert result.params == {"title_contains": "Notepad"}


def test_set_system_volume_has_no_params():
    client = FakeClient(_tool_use_response({"action": "set_system_volume"}))

    result = parse_nl_action("볼륨 조절", PROGRAMS, client=client)

    assert result.action == "set_system_volume"
    assert result.type == "continuous"
    assert result.params == {}


def test_unknown_action_name_returns_none():
    client = FakeClient(_tool_use_response({"action": "delete_all_files"}))

    result = parse_nl_action("...", PROGRAMS, client=client)

    assert result is None


def test_api_error_returns_none():
    client = FakeClient(exc=RuntimeError("network down"))

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS, client=client)

    assert result is None


def test_empty_text_returns_none_without_calling_client():
    client = FakeClient()

    result = parse_nl_action("   ", PROGRAMS, client=client)

    assert result is None
    assert client.messages.last_kwargs is None


def test_missing_api_key_returns_none_without_calling_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = parse_nl_action("카카오톡 열어줘", PROGRAMS)

    assert result is None


def test_call_uses_haiku_model_and_forces_the_tool():
    client = FakeClient(_tool_use_response({"action": "open_url", "url": "https://example.com"}))

    parse_nl_action("open example.com", PROGRAMS, client=client)

    kwargs = client.messages.last_kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["tool_choice"] == {
        "type": "tool",
        "name": "propose_binding",
        "disable_parallel_tool_use": True,
    }


def test_apply_layout_resolves_a_layout_name(monkeypatch):
    import mpk_deck.core.nl_action as nl
    from mpk_deck.core.layout_store import Layout

    monkeypatch.setattr(nl, "load_layouts", lambda: {"coding": Layout(name="코딩 셋업", items=[])})
    client = FakeClient(_tool_use_response({"action": "apply_layout", "layout_name": "코딩 셋업"}))
    binding = parse_nl_action("코딩 레이아웃 열어", [], client=client)
    assert binding is not None
    assert binding.action == "apply_layout"
    assert binding.params == {"layout_id": "coding"}


def test_apply_layout_unknown_name_returns_none(monkeypatch):
    import mpk_deck.core.nl_action as nl

    monkeypatch.setattr(nl, "load_layouts", lambda: {})
    client = FakeClient(_tool_use_response({"action": "apply_layout", "layout_name": "nope"}))
    assert parse_nl_action("x", [], client=client) is None


def test_nl_proposes_display_brightness():
    client = FakeClient(_tool_use_response({"action": "set_display_brightness"}))
    result = parse_nl_action("화면 밝기 조절", PROGRAMS, client=client)
    assert result.action == "set_display_brightness"
    assert result.type == "continuous"
    assert result.params == {}


def test_nl_proposes_shell_command():
    client = FakeClient(_tool_use_response({"action": "run_shell_command", "command": "shutdown /s /t 0"}))
    result = parse_nl_action("컴퓨터 종료 명령", PROGRAMS, client=client)
    assert result.action == "run_shell_command"
    assert result.type == "trigger"
    assert result.params == {"command": "shutdown /s /t 0"}


def test_nl_shell_command_empty_is_rejected():
    client = FakeClient(_tool_use_response({"action": "run_shell_command", "command": "   "}))
    assert parse_nl_action("빈 명령", PROGRAMS, client=client) is None


def test_nl_proposes_media_key():
    client = FakeClient(_tool_use_response({"action": "media_key", "media_key": "next"}))
    result = parse_nl_action("다음 곡", PROGRAMS, client=client)
    assert result.action == "media_key"
    assert result.params == {"key": "next"}


def test_nl_media_key_bad_value_is_rejected():
    client = FakeClient(_tool_use_response({"action": "media_key", "media_key": "rewind"}))
    assert parse_nl_action("되감기", PROGRAMS, client=client) is None

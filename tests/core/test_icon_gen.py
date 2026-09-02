from mpk_deck.core.icon_gen import _looks_safe, generate_icon_svg

_GOOD = '<circle cx="32" cy="32" r="18" fill="none" stroke="{accent}" stroke-width="5"/>'


def test_looks_safe_accepts_a_plain_icon_body():
    assert _looks_safe(_GOOD)
    assert _looks_safe('<rect x="10" y="10" width="20" height="20" stroke="{neutral}"/><path d="M0 0 L5 5" stroke="{accent}"/>')


def test_looks_safe_rejects_script_image_and_external_refs():
    assert not _looks_safe('<script>x()</script>')
    assert not _looks_safe('<image href="http://evil/x.png"/>')
    assert not _looks_safe('<use xlink:href="#x"/>')
    assert not _looks_safe('<rect fill="url(https://evil)"/>')


def test_looks_safe_rejects_entities_and_doctype():
    assert not _looks_safe('<!DOCTYPE svg [<!ENTITY lol "lol">]>')
    assert not _looks_safe('<text>&lol;</text>')
    assert not _looks_safe('<?xml-stylesheet href="x"?>')


def test_looks_safe_rejects_malformed_xml():
    assert not _looks_safe('<rect x="1"')


def test_looks_safe_rejects_oversized_body():
    assert not _looks_safe("<path d='" + "M0 0 " * 2000 + "'/>")


class _FakeBlock:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class _FakeResponse:
    def __init__(self, data):
        self.content = [_FakeBlock(data)]


class _FakeClient:
    def __init__(self, data):
        self._data = data
        self.messages = self

    def create(self, **_kwargs):
        return _FakeResponse(self._data)


def test_generate_icon_svg_returns_body_on_valid_model_output():
    client = _FakeClient({"svg_body": _GOOD})
    assert generate_icon_svg("a circle", client=client) == _GOOD


def test_generate_icon_svg_returns_none_on_unsafe_output():
    client = _FakeClient({"svg_body": '<script>bad()</script>'})
    assert generate_icon_svg("bad", client=client) is None


def test_generate_icon_svg_returns_none_for_blank_description():
    assert generate_icon_svg("   ", client=_FakeClient({"svg_body": _GOOD})) is None


def test_generate_icon_svg_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_icon_svg("something") is None

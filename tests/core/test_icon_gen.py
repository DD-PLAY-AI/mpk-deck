from mpk_deck.core.icon_gen import is_safe_svg_body, generate_icon_svg

_GOOD = '<circle cx="32" cy="32" r="18" fill="none" stroke="{accent}" stroke-width="5"/>'


def test_is_safe_svg_body_accepts_a_plain_icon_body():
    assert is_safe_svg_body(_GOOD)
    assert is_safe_svg_body('<rect x="10" y="10" width="20" height="20" stroke="{neutral}"/><path d="M0 0 L5 5" stroke="{accent}"/>')


def test_is_safe_svg_body_rejects_script_image_and_external_refs():
    assert not is_safe_svg_body('<script>x()</script>')
    assert not is_safe_svg_body('<image href="http://evil/x.png"/>')
    assert not is_safe_svg_body('<use xlink:href="#x"/>')
    assert not is_safe_svg_body('<rect fill="url(https://evil)"/>')


def test_is_safe_svg_body_rejects_entities_and_doctype():
    assert not is_safe_svg_body('<!DOCTYPE svg [<!ENTITY lol "lol">]>')
    assert not is_safe_svg_body('<text>&lol;</text>')
    assert not is_safe_svg_body('<?xml-stylesheet href="x"?>')


def test_is_safe_svg_body_rejects_renderer_dos_surface():
    assert not is_safe_svg_body('<filter id="b"><feGaussianBlur stdDeviation="9999"/></filter><rect filter="url(#b)"/>')
    assert not is_safe_svg_body('<rect><animate attributeName="x" dur="1s" repeatCount="indefinite"/></rect>')
    assert not is_safe_svg_body('<pattern id="p"><rect/></pattern>')
    assert not is_safe_svg_body('<mask id="m"><rect/></mask>')
    assert not is_safe_svg_body('<svg><rect/></svg>')  # nested svg


def test_is_safe_svg_body_rejects_malformed_xml():
    assert not is_safe_svg_body('<rect x="1"')


def test_is_safe_svg_body_rejects_oversized_body():
    assert not is_safe_svg_body("<path d='" + "M0 0 " * 2000 + "'/>")


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

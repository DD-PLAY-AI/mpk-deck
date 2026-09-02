from mpk_deck.core.browser_url import browser_kind


def test_browser_kind_recognises_the_chromium_browsers_and_firefox():
    assert browser_kind(r"C:\Program Files\Google\Chrome\Application\chrome.exe") == "chrome"
    assert browser_kind(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.EXE") == "edge"
    assert browser_kind(r"C:\Program Files\Mozilla Firefox\firefox.exe") == "firefox"


def test_browser_kind_is_none_for_non_browsers_and_blank():
    assert browser_kind(r"C:\Windows\System32\notepad.exe") is None
    assert browser_kind("") is None


def test_normalise_rejects_search_terms_and_adds_scheme():
    from mpk_deck.core.browser_url import _normalise

    assert _normalise("hello world") is None       # has a space -> a search
    assert _normalise("localhost") is None          # no dot -> not a URL
    assert _normalise("example.com/x") == "https://example.com/x"
    assert _normalise("http://a.b") == "http://a.b"

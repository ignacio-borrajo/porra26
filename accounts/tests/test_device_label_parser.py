from accounts.services.sessions import parse_device_label


def test_iphone_safari():
    ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    )
    label = parse_device_label(ua)
    assert "iPhone" in label
    assert "Safari" in label


def test_chrome_macos():
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
        "Safari/537.36"
    )
    label = parse_device_label(ua)
    assert "Chrome" in label
    assert "Mac" in label or "macOS" in label


def test_edge_windows():
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
        "Safari/537.36 Edg/120.0.0.0"
    )
    label = parse_device_label(ua)
    assert "Edge" in label or "Edg" in label
    assert "Windows" in label


def test_empty_user_agent_returns_fallback():
    assert parse_device_label("") == "Dispositivo desconocido"


def test_extremely_long_ua_truncated_safely():
    label = parse_device_label("x" * 5000)
    assert len(label) <= 80

from app.notification.api import _expiry_text


def test_expiry_text():
    assert _expiry_text(1) == "1 hour"
    assert _expiry_text(12) == "12 hours"
    assert _expiry_text(24) == "1 day"
    assert _expiry_text(168) == "7 days"

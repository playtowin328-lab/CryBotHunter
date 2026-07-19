from app.api.routes.auth import _registration_allowed


def test_first_owner_can_register_on_empty_database():
    assert _registration_allowed(user_count=0, registration_enabled=False) is True


def test_additional_registration_is_disabled_by_default():
    assert _registration_allowed(user_count=1, registration_enabled=False) is False


def test_operator_can_explicitly_enable_additional_registration():
    assert _registration_allowed(user_count=1, registration_enabled=True) is True

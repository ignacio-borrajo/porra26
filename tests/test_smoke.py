def test_django_setup_works():
    from django.conf import settings

    assert settings.AUTH_USER_MODEL == "accounts.User"

import pytest


@pytest.fixture(autouse=True)
def _enable_db_for_tests(db):
    """Autoriza acceso a BD en todos los tests."""
    pass


@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    """Aísla MEDIA_ROOT en un directorio temporal para no escribir a disco real."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT

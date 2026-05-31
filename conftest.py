import pytest


@pytest.fixture(autouse=True)
def _enable_db_for_tests(db):
    """Autoriza acceso a BD en todos los tests."""
    pass

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
class TestPreviewPermissions:
    def test_redirects_player_to_dashboard(self, client):
        client.force_login(UserFactory(is_gestor=False))
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 302
        assert reverse("competicion:dashboard") in res.headers["Location"]

    def test_gestor_gets_200(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 200

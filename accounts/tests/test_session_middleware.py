from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _login(client, user, remember="1"):
    data = {"email": user.email, "password": "Secret123"}
    if remember:
        data["remember"] = remember
    client.post(reverse("accounts:login"), data)


def test_middleware_updates_last_seen_for_authenticated_request(client):
    user = UserFactory(email="a@edisa.com", password="Secret123")
    _login(client, user)
    us = UserSession.objects.get(user=user)
    cache.clear()
    UserSession.objects.filter(pk=us.pk).update(last_seen_at=timezone.now() - timedelta(minutes=5))

    client.get(reverse("competicion:dashboard"))

    us.refresh_from_db()
    assert us.last_seen_at > timezone.now() - timedelta(minutes=1)


def test_middleware_renews_expiry_only_when_remembered(client):
    user = UserFactory(email="b@edisa.com", password="Secret123")
    _login(client, user, remember="")
    cache.clear()
    client.get(reverse("competicion:dashboard"))
    assert client.session.get_expire_at_browser_close() is True


def test_middleware_throttle_avoids_double_db_hit(client):
    user = UserFactory(email="c@edisa.com", password="Secret123")
    _login(client, user)
    us = UserSession.objects.get(user=user)

    UserSession.objects.filter(pk=us.pk).update(last_seen_at=timezone.now() - timedelta(hours=1))
    client.get(reverse("competicion:dashboard"))
    us.refresh_from_db()
    assert us.last_seen_at < timezone.now() - timedelta(minutes=30)


def test_middleware_skips_anonymous_requests(client):
    cache.clear()
    resp = client.get(reverse("accounts:login"))
    assert resp.status_code == 200


def test_middleware_safe_with_orphan_session(client):
    user = UserFactory(email="d@edisa.com", password="Secret123")
    _login(client, user)
    UserSession.objects.filter(user=user).delete()
    cache.clear()
    resp = client.get(reverse("competicion:dashboard"))
    assert resp.status_code in (200, 302)

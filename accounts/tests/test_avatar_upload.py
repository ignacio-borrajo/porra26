from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from accounts.models import AuditLog
from accounts.tests.factories import UserFactory


def _png(size=(400, 400), color=(50, 100, 200)) -> SimpleUploadedFile:
    img = Image.new("RGB", size, color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("a.png", buf.read(), content_type="image/png")


def _profile_payload(**overrides):
    base = {
        "action": "profile",
        "name": "Ana",
        "sede": "vigo",
        "puesto": "desarrollo",
        "dept": "gestion",
    }
    base.update(overrides)
    return base


@pytest.mark.django_db
def test_post_uploads_avatar(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {**_profile_payload(), "avatar": _png()},
    )
    assert r.status_code == 302, r.content
    user.refresh_from_db()
    assert user.avatar
    img = Image.open(user.avatar.path)
    assert img.size == (256, 256)
    assert img.format == "JPEG"


@pytest.mark.django_db
def test_post_oversize_rejected(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    big = SimpleUploadedFile("big.png", b"\x89PNG" + b"x" * (3 * 1024 * 1024), content_type="image/png")
    r = client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": big})
    assert r.status_code == 200
    user.refresh_from_db()
    assert not user.avatar


@pytest.mark.django_db
def test_post_invalid_type_rejected(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    bad = SimpleUploadedFile("fake.jpg", b"this is not an image", content_type="image/jpeg")
    r = client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": bad})
    assert r.status_code == 200
    user.refresh_from_db()
    assert not user.avatar


@pytest.mark.django_db
def test_replacement_deletes_old_file(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png(color=(10, 10, 10))})
    user.refresh_from_db()
    old_path = Path(user.avatar.path)
    assert old_path.exists()

    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png(color=(200, 0, 0))})
    user.refresh_from_db()
    new_path = Path(user.avatar.path)
    assert new_path.exists()
    assert new_path != old_path
    assert not old_path.exists()


@pytest.mark.django_db
def test_clear_removes_file_and_field(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png()})
    user.refresh_from_db()
    old_path = Path(user.avatar.path)
    assert old_path.exists()

    r = client.post(
        reverse("accounts:my_account"),
        {**_profile_payload(), "avatar-clear": "on"},
    )
    assert r.status_code == 302
    user.refresh_from_db()
    assert not user.avatar
    assert not old_path.exists()


@pytest.mark.django_db
def test_renders_img_when_avatar_set(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png()})
    r = client.get(reverse("accounts:my_account"))
    assert r.status_code == 200
    body = r.content.decode()
    assert '<img class="avatar"' in body
    assert "/media/avatars/" in body


@pytest.mark.django_db
def test_renders_initials_fallback_when_no_avatar(client):
    user = UserFactory(name="Ana López", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    r = client.get(reverse("accounts:my_account"))
    body = r.content.decode()
    assert '<span class="avatar"' in body
    assert "AL" in body


@pytest.mark.django_db
def test_audit_log_includes_avatar_change(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png()})
    log = AuditLog.objects.filter(action="profile.update").first()
    assert log is not None
    assert "avatar" in log.payload["changed"]


@pytest.mark.django_db
def test_audit_log_includes_avatar_on_clear(client):
    user = UserFactory(name="Ana", sede="vigo", puesto="desarrollo", dept="gestion")
    client.force_login(user)
    client.post(reverse("accounts:my_account"), {**_profile_payload(), "avatar": _png()})
    AuditLog.objects.all().delete()

    client.post(
        reverse("accounts:my_account"),
        {**_profile_payload(), "avatar-clear": "on"},
    )
    log = AuditLog.objects.filter(action="profile.update").first()
    assert log is not None
    assert "avatar" in log.payload["changed"]

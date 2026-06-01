from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, UnidentifiedImageError

from accounts.services.avatar import process_avatar


def _to_upload(img: Image.Image, name: str, fmt: str = "PNG") -> SimpleUploadedFile:
    buf = BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type=f"image/{fmt.lower()}")


def test_process_avatar_resizes_to_256():
    src = Image.new("RGB", (1000, 500), (10, 20, 30))
    f = _to_upload(src, "x.png")
    out = process_avatar(f)
    img = Image.open(out)
    assert img.size == (256, 256)
    assert img.format == "JPEG"


def test_process_avatar_flattens_transparency():
    src = Image.new("RGBA", (300, 300), (255, 0, 0, 128))
    f = _to_upload(src, "x.png")
    out = process_avatar(f)
    img = Image.open(out)
    assert img.mode == "RGB"
    assert img.size == (256, 256)


def test_process_avatar_rejects_non_image():
    f = SimpleUploadedFile("notanimage.jpg", b"plain text not image", content_type="image/jpeg")
    with pytest.raises(UnidentifiedImageError):
        process_avatar(f)


def test_process_avatar_handles_jpeg_input():
    src = Image.new("RGB", (400, 600), (0, 100, 200))
    f = _to_upload(src, "x.jpg", fmt="JPEG")
    out = process_avatar(f)
    img = Image.open(out)
    assert img.size == (256, 256)
    assert img.format == "JPEG"

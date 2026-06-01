from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256
JPEG_QUALITY = 85


def process_avatar(uploaded_file) -> ContentFile:
    """Valida y normaliza una imagen subida a un JPEG cuadrado 256×256.

    Lanza UnidentifiedImageError si el archivo no es una imagen reconocible.
    """
    with Image.open(uploaded_file) as probe:
        probe.verify()
    uploaded_file.seek(0)

    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)

    if img.mode != "RGB":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        bg.paste(img, mask=mask)
        img = bg

    img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return ContentFile(buf.getvalue(), name="avatar.jpg")


__all__ = ["process_avatar", "UnidentifiedImageError"]

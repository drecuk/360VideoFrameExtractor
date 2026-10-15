import io
import time
from pathlib import Path

from PIL import Image, ImageOps


def read_image_bytes(image_path, attempts=3, retry_delay=0.15):
    """Read an image with short retries for transient Windows file locks."""
    path = Path(image_path).expanduser().resolve()
    last_error = None

    for attempt in range(attempts):
        try:
            return path.read_bytes()
        except OSError as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(retry_delay * (attempt + 1))

    raise OSError(f"Could not read {path.name}: {last_error}") from last_error


def create_thumbnail_bytes(image_path, max_dimension=640):
    """Return a display-ready JPEG thumbnail for a local image file."""
    source_bytes = read_image_bytes(image_path)

    with Image.open(io.BytesIO(source_bytes)) as image:
        image.load()
        image = ImageOps.exif_transpose(image)
        image.thumbnail(
            (max_dimension, max_dimension),
            Image.Resampling.LANCZOS,
        )

        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba_image = image.convert("RGBA")
            rgb_image = Image.new("RGB", rgba_image.size, "white")
            rgb_image.paste(rgba_image, mask=rgba_image.getchannel("A"))
            image = rgb_image
        elif image.mode != "RGB":
            image = image.convert("RGB")

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)
        return output.getvalue()

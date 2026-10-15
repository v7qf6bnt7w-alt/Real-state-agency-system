from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

validate_property_media = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp", "mp4", "webm", "pdf", "docx", "svg"]
)


def validate_file_size(value):
    if value.size > 25 * 1024 * 1024:
        raise ValidationError("Files must be 25 MB or smaller.")


def validate_hotspots(value):
    if not isinstance(value, list):
        raise ValidationError("Hotspots must be a list.")
    for hotspot in value:
        if not isinstance(hotspot, dict) or not isinstance(hotspot.get("label"), str):
            raise ValidationError("Each hotspot needs a text label.")
        coords = [hotspot.get(key) for key in ("x", "y", "width", "height")]
        if any(not isinstance(coord, (int, float)) or not 0 <= coord <= 100 for coord in coords):
            raise ValidationError("Hotspot coordinates must be percentages between 0 and 100.")
        if hotspot.get("x", 0) + hotspot.get("width", 0) > 100 or hotspot.get("y", 0) + hotspot.get("height", 0) > 100:
            raise ValidationError("A hotspot must fit inside the floor-plan image.")
        if "details" in hotspot and not isinstance(hotspot["details"], str):
            raise ValidationError("Hotspot details must be text.")

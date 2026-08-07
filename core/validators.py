from django.core.exceptions import ValidationError


MAX_PROFILE_IMAGE_BYTES = 1024 * 1024


def validate_profile_image_size(upload):
    """Reject profile pictures above the shared 1 MB product limit."""
    if upload and getattr(upload, "size", 0) > MAX_PROFILE_IMAGE_BYTES:
        raise ValidationError("حجم الصورة أكبر من الحد المسموح: 1 ميجابايت كحد أقصى.")

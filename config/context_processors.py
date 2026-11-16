from django.conf import settings


def ui(request):
    """Values every template can use."""
    return {"tailwind_cdn": settings.HC_TAILWIND_CDN}

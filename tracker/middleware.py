import logging

from django.db import OperationalError
from django.shortcuts import render

logger = logging.getLogger(__name__)


class DatabaseDownMiddleware:
    """Connectivity feature 8: turn 'cannot reach PostgreSQL' into a friendly 503 page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, OperationalError):
            logger.error("Database unreachable on %s: %s", request.path, exception)
            return render(request, "errors/db_down.html", status=503)
        return None  # any other error: let Django handle it as normal

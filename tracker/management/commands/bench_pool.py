import time
from urllib.request import urlopen

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Connectivity feature 3: compare DB_POOL=True and DB_POOL=False.

    Calls the RUNNING dev server over real HTTP, because Django's test client
    keeps one connection open and would hide the difference.
    """

    help = "Time N requests to /health/db/ on the running dev server."

    def add_arguments(self, parser):
        parser.add_argument("--requests", type=int, default=100)
        parser.add_argument("--url", default="http://127.0.0.1:8000/health/db/")

    def handle(self, *args, **opts):
        n, url = opts["requests"], opts["url"]
        urlopen(url).read()  # warm-up
        start = time.perf_counter()
        for _ in range(n):
            urlopen(url).read()
        elapsed = time.perf_counter() - start
        self.stdout.write(f"{n} requests in {elapsed:.2f} s = {elapsed / n * 1000:.1f} ms each")

"""Run the site locally without Redis: python3 dev_server.py, then open the printed link."""
import os
import pathlib
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT / "api"))
os.environ.setdefault("ACCESS_KEY", "dev")
import index  # noqa: E402

if index.STORE is None:
    index.STORE = index.Memory()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "public"), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api"):
            return index.handler._run(self)
        # same as the rewrite in vercel.json: /<invite key> serves the page
        first = self.path.split("?")[0].strip("/")
        if first and "/" not in first and "." not in first:
            self.path = "/index.html"
        super().do_GET()

    do_PUT = do_POST = do_PATCH = do_DELETE = index.handler._run


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"http://localhost:{port}/{os.environ['ACCESS_KEY']}")
    ThreadingHTTPServer(("", port), Handler).serve_forever()

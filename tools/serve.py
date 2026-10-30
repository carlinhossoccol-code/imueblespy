#!/usr/bin/env python3
"""Serve site/ for local testing, threaded.

Python's default http.server handles one request at a time. With a handful of
subresources that queues, and Lighthouse then reports the delay as the page's
own latency: the full directory page measured 92 with 570 ms of server latency
on the single-threaded server and 100 with 0 ms here. Performance numbers taken
against a serial server are measuring the server.

    python3 -I tools/serve.py [port]
"""
import functools
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        # Never let a stale copy mask a change under test.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    srv = ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=ROOT))
    print(f"serving {ROOT} at http://127.0.0.1:{port}  (ctrl-c to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Tiny standard-library web server that serves ONLY the viewer/ folder.

Usage:
    python3 server.py

Serves on http://localhost:4700
"""

import functools
import http.server
import os

PORT = 4700

VIEWER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer")


def main():
    if not os.path.isdir(VIEWER_DIR):
        raise SystemExit(
            f"viewer/ directory not found at {VIEWER_DIR}. "
            "Run build.py first to generate viewer/graph-data.js."
        )

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=VIEWER_DIR
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)

    print(f"Serving {VIEWER_DIR} at http://localhost:{PORT}/")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

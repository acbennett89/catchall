"""Open the ratings site in one step: build the page if it is missing or out of date, serve it on
this computer only, and open it in your browser.

    python launch.py               open the site (close the window, or press Ctrl+C, to stop)
    python launch.py --update      first download the current season's new games and polls and
                                   rebuild that season (needs the internet; `requests` is installed
                                   if missing), then open the site
    python launch.py --no-browser  serve without opening a browser tab
    python launch.py --no-serve    do the building/updating only

On Windows, double-click "Launch CFB Rankings.bat" or "Update CFB Rankings.bat" instead.
"""
import argparse
import functools
import glob
import gzip
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "out", "site")
PAGE_INPUTS = ("report.py", "report_template.html", "METRICS.md", "ADVERSARIAL_REVIEW.md", "TRACE.md",
               "config.json")


def step(*args):
    """Run one pipeline script as its own process, exactly as if typed at the prompt."""
    print("\n> python " + " ".join(args), flush=True)
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"}
    if subprocess.call([sys.executable, *args], cwd=HERE, env=env):
        raise SystemExit(f"\n'python {' '.join(args)}' failed (see above).")


def page_is_stale():
    """True when out/site/index.html is missing or older than anything it is built from."""
    page = os.path.join(SITE, "index.html")
    if not os.path.exists(page):
        return True
    inputs = [os.path.join(HERE, f) for f in PAGE_INPUTS]
    for pattern in ("ratings.json", "weekly.json", "traces/*.json", "traces/internal/*.json"):
        inputs += glob.glob(os.path.join(HERE, "out", "[0-9]*", pattern))
    built = os.path.getmtime(page)
    return any(os.path.getmtime(p) > built for p in inputs if os.path.exists(p))


def update():
    """Download the current season's games and polls (cached ones are reused) and rebuild it."""
    try:
        import requests  # noqa: F401  (only the downloaders need it)
    except ImportError:
        step("-m", "pip", "install", "--user", "--disable-pip-version-check", "--no-warn-script-location",
             "requests")
    season = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))["season"]
    weeks = 16
    try:  # the season's own calendar, from the last download
        with gzip.open(os.path.join(HERE, "data", str(season), "games.json.gz"), "rt", encoding="utf-8") as f:
            weeks = json.load(f).get("calendar", {}).get("regular_season_weeks") or weeks
    except (OSError, EOFError, ValueError):
        pass
    print(f"Updating {season}: weeks 1-{weeks} from ESPN. The first run on a new computer downloads "
          "every game so far and takes several minutes; later runs fetch only new games.")
    step("fetch.py", "--season", str(season), "--weeks", f"1-{weeks}")
    step("parse.py", "--season", str(season))
    step("polls.py", "--season", str(season))
    step("build.py", "--season", str(season))


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = False  # never share a port with another program

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: and keep others off this one
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], ConnectionError):
            return  # the browser cancelled a download (a reload, a quick season switch): not an error
        super().handle_error(request, client_address)


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # a rebuilt page shows on the next reload
        super().end_headers()

    def log_message(self, *args):
        pass  # keep the window quiet


def no_quick_edit():
    """Windows consoles pause a running program when you click in them (QuickEdit) until a key is
    pressed, which looks like a hang. Turn that off for this window."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h, mode = k.GetStdHandle(-10), ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)  # QUICK_EDIT off, EXTENDED_FLAGS on
    except Exception:
        pass


def serve(port, open_browser):
    handler = functools.partial(Handler, directory=SITE)
    httpd = None
    for p in list(range(port, port + 20)) + [0]:  # 0: any free port the system picks
        try:
            httpd = Server(("127.0.0.1", p), handler)
            break
        except OSError:
            continue
    if httpd is None:
        raise SystemExit("Could not open a local port for the site.")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"\nFBS Efficiency Ratings: {url}\nOnly this computer can see it. Leave this window open while "
          "you use the site; close it to stop.", flush=True)
    if open_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--update", action="store_true", help="download new games and polls first")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-serve", action="store_true")
    a = ap.parse_args()
    if sys.version_info < (3, 8):
        sys.exit(f"Python 3.8 or newer is needed (this is {sys.version.split()[0]}).")
    no_quick_edit()
    try:
        if a.update:
            try:
                update()
            except SystemExit as e:
                # build.py swaps its outputs in only when it finishes, so the last good ratings stand.
                print(f"{e}\nThe update did not finish. Showing the ratings from before it.", flush=True)
        if a.update or page_is_stale():
            step("report.py")
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
    if not a.no_serve:
        serve(a.port, not a.no_browser)


if __name__ == "__main__":
    main()

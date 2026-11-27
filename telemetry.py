"""Optional, anonymous usage statistics for the Hacker Cam desktop app (PostHog).

Nothing is sent unless BOTH are true:
  * a PostHog project key is set (POSTHOG_KEY below, or HACKERCAM_POSTHOG_KEY), and
  * the user said yes when the app asked (or ticked the box in Options).
DO_NOT_TRACK=1 or HACKERCAM_NO_TELEMETRY=1 turns it off regardless.

What is sent: an event name ("app_started", "effect_used", ...), the app version,
OS and CPU type, the effect's name, and a random install ID made on this
computer. Never video, images, your name or title, camera names, or anything
you type. Events don't create PostHog person profiles.

Uses only the standard library. Sending happens on a background thread, in
batches, and failures are ignored: analytics never slows down or breaks the app.
"""
import json
import os
import platform
import queue
import ssl
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone

# The project API key is write-only and safe to publish (websites embed theirs).
# Leave empty to build an app that never sends anything.
POSTHOG_KEY = ""
POSTHOG_HOST = "https://us.i.posthog.com"      # EU projects: https://eu.i.posthog.com


def configured_key():
    return os.environ.get("HACKERCAM_POSTHOG_KEY", POSTHOG_KEY).strip()


def blocked_by_env():
    return any(os.environ.get(v, "").strip() not in ("", "0", "false")
               for v in ("DO_NOT_TRACK", "HACKERCAM_NO_TELEMETRY"))


def available():
    """True if this build could send stats at all (so it's worth asking)."""
    return bool(configured_key()) and not blocked_by_env()


def _ssl_context():
    try:                     # packaged apps may not find the system CA store
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class Telemetry:
    FLUSH_EVERY = 30.0       # seconds
    MAX_BATCH = 50

    def __init__(self, install_id, version, enabled=False):
        self.install_id = install_id
        self.key = configured_key()
        self.host = os.environ.get("HACKERCAM_POSTHOG_HOST", POSTHOG_HOST).rstrip("/")
        self.base = {
            "app_version": version,
            "os": platform.system(),            # Darwin / Windows / Linux
            "os_version": platform.release(),
            "arch": platform.machine(),
            "$process_person_profile": False,   # anonymous: no person profiles
        }
        self._queue = queue.SimpleQueue()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self.enabled = False
        self.set_enabled(enabled)

    @staticmethod
    def new_install_id():
        return str(uuid.uuid4())

    def set_enabled(self, on):
        self.enabled = bool(on) and available()
        if self.enabled and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="telemetry", daemon=True)
            self._thread.start()

    def capture(self, event, **props):
        """Queue an event. Cheap and safe to call from any thread."""
        if not self.enabled:
            return
        self._queue.put({
            "event": event,
            "properties": {**self.base, **props, "distinct_id": self.install_id},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def close(self, timeout=2.0):
        """Send what's queued (briefly) and stop."""
        if self._thread is None:
            return
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout)

    # --- background thread --------------------------------------------------

    def _loop(self):
        ctx = _ssl_context()
        while True:
            self._wake.wait(self.FLUSH_EVERY)
            self._wake.clear()
            self._flush(ctx)
            if self._stop.is_set():
                return

    def _flush(self, ctx):
        while True:
            batch = []
            while len(batch) < self.MAX_BATCH:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if not batch:
                return
            if not self.enabled:            # switched off: drop what was queued
                continue
            body = json.dumps({"api_key": self.key, "batch": batch}).encode()
            req = urllib.request.Request(f"{self.host}/batch/", data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=5, context=ctx).close()
            except Exception:
                return                      # offline or blocked: drop it, try later events


class Session:
    """Tracks how long the app was used, for the app_quit event."""

    def __init__(self):
        self.started = time.monotonic()

    def minutes(self):
        return round((time.monotonic() - self.started) / 60, 1)

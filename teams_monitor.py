"""Teams notification watcher for Windows.

This script tails the Microsoft Teams log file and emits notifications
when the badge count for unread activity becomes greater than zero.

It is designed to run on Windows.  On other operating systems the
notification features fall back to console output.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

try:  # pragma: no cover - optional on non-Windows platforms
    import winsound  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - optional on non-Windows platforms
    winsound = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from win10toast import ToastNotifier  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    ToastNotifier = None  # type: ignore


BADGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\"missedActivityCount\"\s*:\s*(\d+)", re.IGNORECASE),
    re.compile(r"\"badgeCount\"\s*:\s*(\d+)", re.IGNORECASE),
    re.compile(r"badge count[^0-9]*(\d+)", re.IGNORECASE),
)


@dataclass
class NotificationConfig:
    """Configuration for how notifications should be presented."""

    use_toast: bool = True
    use_sound: bool = True
    quiet_reset: bool = False
    toast_duration: int = 5


class TeamsNotifier:
    """Dispatches notifications using the available backends."""

    def __init__(self, config: NotificationConfig) -> None:
        self.config = config
        self._toast = None
        if config.use_toast and ToastNotifier is not None:
            try:
                self._toast = ToastNotifier()
            except Exception as exc:  # pragma: no cover - environment specific
                print(
                    f"Failed to initialise toast notifications: {exc}",
                    file=sys.stderr,
                )
                self._toast = None

    def _play_sound(self) -> None:
        if not self.config.use_sound:
            return
        if winsound is None:  # pragma: no cover - Windows only
            return
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:  # pragma: no cover - Windows only
            pass

    def notify(self, title: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {title}: {message}")
        self._play_sound()
        if self._toast is not None:
            try:  # pragma: no cover - requires Windows
                self._toast.show_toast(
                    title,
                    message,
                    duration=self.config.toast_duration,
                    threaded=True,
                )
            except Exception as exc:
                print(
                    f"Failed to show toast notification: {exc}",
                    file=sys.stderr,
                )


class TeamsLogWatcher:
    """Watches the Teams log file for changes in the badge count."""

    def __init__(
        self,
        log_path: Path,
        notifier: TeamsNotifier,
        poll_interval: float = 2.0,
        patterns: Iterable[re.Pattern[str]] = BADGE_PATTERNS,
    ) -> None:
        self.log_path = log_path
        self.notifier = notifier
        self.poll_interval = poll_interval
        self.patterns = tuple(patterns)
        self._stop_event = threading.Event()
        self._last_badge_count: Optional[int] = None

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        """Start watching the log file until :meth:`stop` is called."""

        if not self.log_path.exists():
            raise FileNotFoundError(
                f"Teams log file not found at '{self.log_path}'. "
                "Make sure Microsoft Teams is installed and has run at least once."
            )

        with self.log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            # Seek to the end of the file so we only read new entries going forward.
            handle.seek(0, os.SEEK_END)
            while not self._stop_event.is_set():
                position = handle.tell()
                line = handle.readline()
                if not line:
                    handle.seek(position)
                    time.sleep(self.poll_interval)
                    continue
                self._process_line(line)

    def _process_line(self, line: str) -> None:
        badge_count = self._extract_badge_count(line)
        if badge_count is None:
            return

        previous = self._last_badge_count
        self._last_badge_count = badge_count
        if previous == badge_count:
            return

        if badge_count > 0:
            plural = "s" if badge_count != 1 else ""
            self.notifier.notify(
                "Teams notification",
                f"You have {badge_count} unread item{plural}.",
            )
        elif previous and not self.notifier.config.quiet_reset:
            self.notifier.notify(
                "Teams notification",
                "All Teams notifications have been cleared.",
            )

    def _extract_badge_count(self, line: str) -> Optional[int]:
        for pattern in self.patterns:
            match = pattern.search(line)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None


def default_log_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError(
            "The APPDATA environment variable is not set. "
            "This script must be run on Windows."
        )
    return Path(appdata) / "Microsoft" / "Teams" / "logs.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Watch the Microsoft Teams log file for badge count changes "
            "and emit local notifications."
        )
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=None,
        help=(
            "Path to the Teams logs.txt file. Defaults to the location under %APPDATA%."
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds to wait before checking for new log entries.",
    )
    parser.add_argument(
        "--no-toast",
        action="store_true",
        help="Disable Windows toast notifications (console output still shown).",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        help="Disable the audible notification.",
    )
    parser.add_argument(
        "--quiet-reset",
        action="store_true",
        help="Do not emit a notification when the badge count returns to zero.",
    )
    parser.add_argument(
        "--toast-duration",
        type=int,
        default=5,
        help="Number of seconds a toast notification should remain visible.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_path = args.log_path or default_log_path()
    config = NotificationConfig(
        use_toast=not args.no_toast,
        use_sound=not args.no_sound,
        quiet_reset=args.quiet_reset,
        toast_duration=args.toast_duration,
    )
    notifier = TeamsNotifier(config)
    watcher = TeamsLogWatcher(
        log_path=log_path,
        notifier=notifier,
        poll_interval=args.poll_interval,
    )

    try:
        watcher.run()
    except KeyboardInterrupt:
        watcher.stop()
        print("Stopped by user.")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entrypoint
    sys.exit(main())

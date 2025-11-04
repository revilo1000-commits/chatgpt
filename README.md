# Teams notification watcher

This repository provides a small Python script that can monitor the
Microsoft Teams desktop application's log file on Windows. When new
activity is detected (for example unread chats, mentions, or other
notifications that increase the badge count) the script can trigger a
Windows toast notification, play a sound, and print a console message.

## Requirements

* Python 3.9 or later.
* Windows 10/11 (the toast and sound integrations depend on Windows APIs).
* The [`win10toast`](https://pypi.org/project/win10toast/) package for toast
  notifications. Install the requirement with:

  ```powershell
  py -m pip install -r requirements.txt
  ```

  Toast notifications are optional; if the package is missing the script will
  fall back to console output.

## Usage

1. Ensure Microsoft Teams has been opened at least once so that the
   `%APPDATA%\Microsoft\Teams\logs.txt` file exists.
2. Open a terminal (PowerShell or Command Prompt) and run:

   ```powershell
   py teams_monitor.py
   ```

   The script tails the log file and notifies you whenever the unread badge
   count increases. Press `Ctrl+C` to stop it.

### Command line options

```
usage: teams_monitor.py [-h] [--log-path LOG_PATH] [--poll-interval POLL_INTERVAL]
                        [--no-toast] [--no-sound] [--quiet-reset]
                        [--toast-duration TOAST_DURATION]
```

* `--log-path` – Override the path to `logs.txt` if Teams is installed in a
  non-standard location.
* `--poll-interval` – Seconds to wait before checking for new log lines
  (default: `2.0`).
* `--no-toast` – Disable Windows toast notifications; useful if you only want
  console output or audio alerts.
* `--no-sound` – Suppress the audible alert.
* `--quiet-reset` – Do not emit a message when the badge count returns to zero.
* `--toast-duration` – How long the toast should stay visible, in seconds
  (default: `5`).

### Customising the badge detection

Teams occasionally changes the exact log messages it writes. The script looks
for common patterns such as `missedActivityCount`, `badgeCount`, and "badge
count" text. If you notice badge updates are not detected, you can modify the
`BADGE_PATTERNS` tuple near the top of `teams_monitor.py` to add a regular
expression that matches the new log line.

## Troubleshooting

* **`FileNotFoundError: Teams log file not found`** – Launch Microsoft Teams at
  least once so it creates `logs.txt`, or specify the log path manually with
  `--log-path`.
* **No toast notifications** – Make sure you have installed the `win10toast`
  package. If toast notifications still do not appear, the script will log any
  errors it encounters while attempting to display them.
* **No sound** – The audio alert relies on the Windows `winsound` module, so it
  is only available on Windows.

## Limitations

This approach depends on the format of the local Teams log file, which is
subject to change by Microsoft. It also only detects notifications that affect
the application badge count; it does not distinguish between channels or chat
messages.

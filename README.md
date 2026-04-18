# ProbiusOfficial X Reply Notifier

A ProbiusOfficial-focused Python monitor for
`https://x.com/ProbiusOfficial/with_replies`.

It opens X in Chrome through Selenium, tracks recent posts/replies from
`@ProbiusOfficial` by default, stores seen post IDs locally, alerts in the
terminal, plays a local beep, and can optionally send Feishu or DingTalk webhook
notifications.

The monitored account is still configurable. Change `TARGET_USERNAME` in `.env`
to monitor any other X/Twitter account.

## Features

- Watches `@ProbiusOfficial`'s `with_replies` timeline by default.
- Can be repointed to another X/Twitter account with one `.env` change.
- Tracks multiple recent post IDs to reduce duplicate alerts after restarts.
- Rebuilds the Chrome driver after recoverable browser failures.
- Uses a temporary writable Chrome profile by default.
- Can reuse an existing Chrome profile when X login state is required.
- Supports optional Feishu and DingTalk webhook notifications.

## Requirements

- Python 3.10+
- Google Chrome
- Windows, macOS, or Linux
- Docker, if you want to run the monitor in a container

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
copy .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

By default, `.env.example` monitors `@ProbiusOfficial`:

```dotenv
TARGET_USERNAME=ProbiusOfficial
```

Do not commit `.env`; it may contain local paths, login profile locations, and
webhook secrets.

## Monitor Another Account

This project defaults to `@ProbiusOfficial`, but it is not hardcoded to that
account. To monitor another account:

1. Open `.env`.
2. Replace `TARGET_USERNAME` with the account username, with or without `@`.
3. Restart the monitor.

Examples:

```dotenv
TARGET_USERNAME=elonmusk
```

```dotenv
TARGET_USERNAME=@OpenAI
```

The script normalizes the leading `@`, so both forms work. After changing the
target, delete `state/last_seen.json` if you want the new account to start with a
fresh baseline instead of reusing state from the previous target.

## Run

```bash
python monitor.py
```

On the first run, if no previous state exists, the current recent posts are saved
as the baseline and future changes trigger alerts.

## Run With Docker

Create `.env` first:

```bash
copy .env.example .env
```

Edit `.env` if you want to monitor an account other than `@ProbiusOfficial`.

Build and start the container:

```bash
docker compose up --build -d
```

Watch logs:

```bash
docker compose logs -f
```

Stop the container:

```bash
docker compose down
```

The compose setup runs Chromium in headless mode and persists runtime files to
local `state/`, `logs/`, and `diagnostics/` folders. The `.env` file is passed
at runtime and is not copied into the Docker image. Local host Chrome profile
settings are cleared by the default compose file because Windows or macOS Chrome
profile paths do not work inside the Linux container.

By default, Docker build and runtime traffic use the host machine proxy at:

```dotenv
HOST_PROXY_URL=http://host.docker.internal:7890
```

`host.docker.internal` is the hostname containers use to reach the Docker host.
If your proxy uses another port or protocol, update `HOST_PROXY_URL` in `.env`.

## Configuration

All configuration is read from `.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `TARGET_USERNAME` | required | X username to monitor, with or without `@`. |
| `CHECK_INTERVAL_SECONDS` | `60` | Base polling interval. |
| `CHECK_JITTER_SECONDS` | `10` | Random jitter added to the polling interval. |
| `PAGE_LOAD_TIMEOUT_SECONDS` | `45` | Selenium page load timeout. |
| `RECENT_POST_COUNT` | `5` | Number of recent authored posts to track. |
| `STATE_FILE` | `state/last_seen.json` | Local state file path. |
| `LOG_FILE` | `logs/monitor.log` | Local log file path. |
| `DIAGNOSTICS_DIR` | `diagnostics` | Directory for browser diagnostics when scraping fails. |
| `DIAGNOSTICS_INTERVAL_SECONDS` | `300` | Minimum seconds between diagnostic captures. Use `0` to capture every recoverable browser failure. |
| `DIAGNOSTICS_HTML_MAX_CHARS` | `500000` | Maximum page-source characters saved per diagnostic HTML file. Use `0` to save full HTML. |
| `ENABLE_BEEP` | `true` | Enables local sound alerts. |
| `CHROME_BINARY` | empty | Optional Chrome or Chromium executable path. Docker uses `/usr/bin/chromium`. |
| `HOST_PROXY_URL` | `http://host.docker.internal:7890` | Docker compose proxy URL for image build, Python HTTP traffic, and Chromium. |
| `CHROME_HEADLESS` | `false` | Runs Chrome in headless mode. Docker compose sets this to `true`. |
| `CHROME_NO_SANDBOX` | `false` | Adds Chrome's `--no-sandbox` flag. Docker compose sets this to `true`. |
| `CHROME_DISABLE_DEV_SHM_USAGE` | `false` | Adds Chrome's `--disable-dev-shm-usage` flag. Docker compose sets this to `true`. |
| `CHROME_PROXY_SERVER` | empty | Optional Chrome `--proxy-server` value. Docker compose sets it from `HOST_PROXY_URL`. |
| `CHROME_USER_DATA_DIR` | empty | Optional Chrome user data directory for reusing login state. |
| `CHROME_PROFILE_DIRECTORY` | empty | Optional Chrome profile name, such as `Default` or `Profile 1`. |
| `STARTUP_LOGIN_WAIT_SECONDS` | `0` | Optional startup wait for manual login before the first scrape. |
| `FEISHU_WEBHOOK` | empty | Optional Feishu bot webhook URL. |
| `DINGTALK_WEBHOOK` | empty | Optional DingTalk bot webhook URL. |

## Notes

X may require login or change its page structure at any time. If the page shows a
login wall, set `CHROME_USER_DATA_DIR` and `CHROME_PROFILE_DIRECTORY` to a Chrome
profile where you are already logged in.

Docker headless mode is best for accounts/pages that do not require an
interactive login. If X requires login, use a logged-in Chrome profile locally or
edit `docker-compose.yml` to mount a Linux Chrome profile into the container and
point `CHROME_USER_DATA_DIR` at that mounted path.

Use this project responsibly and make sure your usage complies with X's terms and
applicable laws.

## Troubleshooting

If the monitor repeatedly logs `Recoverable browser error`, check the latest files
in `diagnostics/`. Each diagnostic capture may include:

- a `.json` metadata file with the current URL, page title, target URL, and saved file paths
- a `.html` page-source snapshot, truncated by `DIAGNOSTICS_HTML_MAX_CHARS`
- a `.png` screenshot when Chromium can capture one

Common causes are:

- X is showing a login wall or anti-automation page
- the target account has no visible posts in the current session
- the page structure changed and `article[data-testid="tweet"]` no longer matches
- a container is running headless without a logged-in Linux Chrome profile

Docker headless mode is convenient for deployment, but it is not a guaranteed
replacement for a logged-in desktop Chrome session. If X requires login, first
verify the monitor locally with a logged-in Chrome profile, then mount an
equivalent Linux Chrome profile into the container if you need Docker deployment.

## CI

GitHub Actions runs on pushes and pull requests. The workflow installs Python
dependencies, checks `monitor.py` syntax, validates Docker Compose, and builds the
Docker image.

## License

MIT

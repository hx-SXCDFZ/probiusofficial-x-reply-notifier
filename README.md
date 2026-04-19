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
- Can import X login cookies into a persistent Docker Chromium profile without
  using noVNC.
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

## First Deployment Checklist

- [ ] Copy `.env.example` to `.env`.
- [ ] Set `TARGET_USERNAME` to the X account you want to monitor. The default is
  `ProbiusOfficial`.
- [ ] Choose one runtime mode: local Python with `python monitor.py`, Docker with
  the prebuilt GHCR image, or Docker with `docker compose up --build -d`.
- [ ] Confirm proxy settings. Keep
  `HOST_PROXY_URL=http://host.docker.internal:7890` for a host proxy on port
  `7890`, change it for a different proxy, or set `HOST_PROXY_URL=` to disable
  proxy use.
- [ ] Configure notifications. Set `FEISHU_WEBHOOK` to a Feishu/Lark custom bot
  webhook URL for Feishu alerts, leave it empty to disable Feishu, and set
  `DINGTALK_WEBHOOK` only if you also want DingTalk alerts.
- [ ] Keep `.env` private. It may contain webhook secrets and local profile
  paths.
- [ ] Start the monitor, then check `logs/monitor.log` for local runs or
  `logs/docker-monitor.log` for Docker runs.
- [ ] If X shows a login wall, verify the monitor locally with a logged-in
  Chrome profile before relying on Docker headless mode, or import X cookies
  into the Docker Chromium profile.

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

Use the prebuilt GHCR image:

```bash
docker compose pull
docker compose up -d
```

Or build locally and start the container:

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
local `state/`, `logs/`, and `diagnostics/` folders. It also mounts
`docker-chrome-profile/` as a persistent Linux Chromium profile for Docker.
Docker writes its log file to `logs/docker-monitor.log`, while local Python runs
use `logs/monitor.log` by default. The `.env` file is passed at runtime and is
not copied into the Docker image. Local host Chrome profile settings are not used
inside the Linux container because Windows or macOS Chrome profile paths do not
work there.

### Import X Login Cookies Without noVNC

If Docker headless mode reaches a login wall, export X cookies from a logged-in
browser session to `secrets/x-cookies.json`, then import them into the persistent
Docker Chromium profile:

```bash
docker compose --profile tools run --rm cookie-import
```

The helper reads `secrets/x-cookies.json`, writes the cookies into
`docker-chrome-profile/`, and opens the target X page once to persist the login
state. Both `secrets/` and `docker-chrome-profile/` are local-only and ignored by
Git.

By default, Docker build and runtime traffic use the host machine proxy at:

```dotenv
HOST_PROXY_URL=http://host.docker.internal:7890
```

`host.docker.internal` is the hostname containers use to reach the Docker host.
If your proxy uses another port or protocol, update `HOST_PROXY_URL` in `.env`.
If you do not need a proxy, set `HOST_PROXY_URL=` in `.env`.

## Container Images

Release images are published to GitHub Container Registry:

```text
ghcr.io/hx-sxcdfz/probiusofficial-x-reply-notifier
```

Stable releases publish these tags:

- the exact release tag, such as `v0.1.3`
- the semantic version without `v`, such as `0.1.3`
- the minor version, such as `0.1`
- `latest`

Pull a specific release:

```bash
docker pull ghcr.io/hx-sxcdfz/probiusofficial-x-reply-notifier:v0.1.3
```

For reproducible deployments, pin `DOCKER_IMAGE` in `.env` to a release tag:

```dotenv
DOCKER_IMAGE=ghcr.io/hx-sxcdfz/probiusofficial-x-reply-notifier:v0.1.3
```

## Configuration

All configuration is read from `.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `TARGET_USERNAME` | required | X username to monitor, with or without `@`. |
| `DOCKER_IMAGE` | `ghcr.io/hx-sxcdfz/probiusofficial-x-reply-notifier:latest` | Docker image used by Docker Compose. Pin this to a release tag for reproducible deployments. |
| `DOCKER_CHROME_USER_DATA_DIR` | `/app/docker-chrome-profile` | Persistent Linux Chromium profile path used by Docker Compose. |
| `X_COOKIE_FILE` | `/app/secrets/x-cookies.json` | Cookie JSON path used by the Docker cookie-import helper. |
| `CHECK_INTERVAL_SECONDS` | `60` | Base polling interval. |
| `CHECK_JITTER_SECONDS` | `10` | Random jitter added to the polling interval. |
| `PAGE_LOAD_TIMEOUT_SECONDS` | `45` | Selenium page load timeout. |
| `RECENT_POST_COUNT` | `5` | Number of recent authored posts to track. |
| `STATE_FILE` | `state/last_seen.json` | Local state file path. |
| `LOG_FILE` | `logs/monitor.log` | Local log file path. Docker Compose overrides this to `/app/logs/docker-monitor.log`. |
| `DIAGNOSTICS_DIR` | `diagnostics` | Directory for browser diagnostics when scraping fails. |
| `DIAGNOSTICS_INTERVAL_SECONDS` | `300` | Minimum seconds between diagnostic captures. Use `0` to capture every recoverable browser failure. |
| `DIAGNOSTICS_HTML_MAX_CHARS` | `500000` | Maximum page-source characters saved per diagnostic HTML file. Use `0` to save full HTML. |
| `ENABLE_BEEP` | `true` | Enables local sound alerts. |
| `CHROME_BINARY` | empty | Optional Chrome or Chromium executable path. Docker uses `/usr/bin/chromium`. |
| `HOST_PROXY_URL` | `http://host.docker.internal:7890` | Docker compose proxy URL for image build, Python HTTP traffic, and Chromium. Set this to an empty value to disable the proxy. |
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
import X cookies into the Docker Chromium profile with the `cookie-import`
service.

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
verify the monitor locally with a logged-in Chrome profile, then import cookies
into the persistent Docker Chromium profile if you need Docker deployment.

## CI

GitHub Actions runs on pushes and pull requests. The workflow installs Python
dependencies, checks `monitor.py` syntax, validates Docker Compose, and builds the
Docker image. A separate release workflow publishes Docker images to GHCR when a
GitHub release is published, and can also be run manually for an existing tag.

## License

MIT

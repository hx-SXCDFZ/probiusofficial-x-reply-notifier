# Product Requirements: ProbiusOfficial X Reply Notifier

## Background

The project monitors `@ProbiusOfficial`'s X `with_replies` page by default and
alerts the operator when new authored posts or replies appear. The monitored
account remains configurable through `TARGET_USERNAME`.

## Goals

- Monitor `https://x.com/ProbiusOfficial/with_replies` through a real Chrome browser by default.
- Allow users to change `TARGET_USERNAME` to monitor another account.
- Extract recent authored post IDs, URLs, timestamps, and text.
- Persist local state to avoid duplicate alerts across restarts.
- Alert locally and optionally push notifications to Feishu or DingTalk.
- Recover from common Selenium, page load, and browser session failures.

## Core Requirements

| Area | Requirement | Priority |
| --- | --- | --- |
| Browser automation | Launch Chrome through Selenium with a writable profile by default. | P0 |
| Login reuse | Allow an existing Chrome profile to be configured for login reuse. | P0 |
| Content extraction | Extract recent posts authored by the configured target account. | P0 |
| State tracking | Store recent seen IDs in a local JSON state file. | P0 |
| Local alerts | Print highlighted terminal alerts and play an optional beep. | P1 |
| Recovery | Recreate the driver after recoverable browser failures. | P1 |
| Webhooks | Push alert text to Feishu or DingTalk when configured. | P2 |

## Acceptance Criteria

1. The script starts on Windows with Python 3.10+ and Google Chrome installed.
2. When no Chrome profile is configured, the script creates a temporary writable
   profile and avoids Chrome preference write errors.
3. When a configured target publishes a new post or reply, the script detects it
   within one polling cycle after the page refreshes.
4. Runtime state is written to `state/last_seen.json` by default.
5. Logs are written to `logs/monitor.log` by default.
6. `.env`, logs, state files, browser profiles, and driver caches are not tracked
   by Git.

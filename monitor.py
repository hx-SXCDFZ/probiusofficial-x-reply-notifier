import json
import logging
import os
import random
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib import error as url_error
from urllib import request as url_request

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@dataclass
class Config:
    target_username: str
    check_interval_seconds: int = 60
    check_jitter_seconds: int = 10
    page_load_timeout_seconds: int = 45
    recent_post_count: int = 5
    state_file: Path = Path("state/last_seen.json")
    log_file: Path = Path("logs/monitor.log")
    diagnostics_dir: Path = Path("diagnostics")
    diagnostics_interval_seconds: int = 300
    diagnostics_html_max_chars: int = 500_000
    enable_beep: bool = True
    chrome_binary: Optional[str] = None
    chrome_headless: bool = False
    chrome_no_sandbox: bool = False
    chrome_disable_dev_shm_usage: bool = False
    chrome_proxy_server: Optional[str] = None
    chrome_user_data_dir: Optional[str] = None
    chrome_profile_directory: Optional[str] = None
    feishu_webhook: Optional[str] = None
    dingtalk_webhook: Optional[str] = None
    startup_login_wait_seconds: int = 0

    @property
    def target_url(self) -> str:
        return f"https://x.com/{self.target_username}/with_replies"


_TEMP_PROFILE_DIRS: list[str] = []


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    load_dotenv()

    target_username = os.getenv("TARGET_USERNAME", "").strip().lstrip("@")
    if not target_username:
        raise ValueError("TARGET_USERNAME is required. Set it in .env")

    return Config(
        target_username=target_username,
        check_interval_seconds=int(os.getenv("CHECK_INTERVAL_SECONDS", "60")),
        check_jitter_seconds=int(os.getenv("CHECK_JITTER_SECONDS", "10")),
        page_load_timeout_seconds=int(os.getenv("PAGE_LOAD_TIMEOUT_SECONDS", "45")),
        recent_post_count=max(1, int(os.getenv("RECENT_POST_COUNT", "5"))),
        state_file=Path(os.getenv("STATE_FILE", "state/last_seen.json")),
        log_file=Path(os.getenv("LOG_FILE", "logs/monitor.log")),
        diagnostics_dir=Path(os.getenv("DIAGNOSTICS_DIR", "diagnostics")),
        diagnostics_interval_seconds=max(0, int(os.getenv("DIAGNOSTICS_INTERVAL_SECONDS", "300"))),
        diagnostics_html_max_chars=max(0, int(os.getenv("DIAGNOSTICS_HTML_MAX_CHARS", "500000"))),
        enable_beep=env_bool("ENABLE_BEEP", True),
        chrome_binary=(os.getenv("CHROME_BINARY") or "").strip() or None,
        chrome_headless=env_bool("CHROME_HEADLESS", False),
        chrome_no_sandbox=env_bool("CHROME_NO_SANDBOX", False),
        chrome_disable_dev_shm_usage=env_bool("CHROME_DISABLE_DEV_SHM_USAGE", False),
        chrome_proxy_server=(os.getenv("CHROME_PROXY_SERVER") or "").strip() or None,
        chrome_user_data_dir=(os.getenv("CHROME_USER_DATA_DIR") or "").strip() or None,
        chrome_profile_directory=(os.getenv("CHROME_PROFILE_DIRECTORY") or "").strip() or None,
        feishu_webhook=(os.getenv("FEISHU_WEBHOOK") or "").strip() or None,
        dingtalk_webhook=(os.getenv("DINGTALK_WEBHOOK") or "").strip() or None,
        startup_login_wait_seconds=int(os.getenv("STARTUP_LOGIN_WAIT_SECONDS", "0")),
    )


def setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _cleanup_temp_profiles() -> None:
    for temp_dir in list(_TEMP_PROFILE_DIRS):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        finally:
            if temp_dir in _TEMP_PROFILE_DIRS:
                _TEMP_PROFILE_DIRS.remove(temp_dir)


def build_driver(config: Config) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=en-US")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-debugging-port=0")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if config.chrome_headless:
        options.add_argument("--headless=new")
        logging.info("Chrome headless mode is enabled")

    if config.chrome_no_sandbox:
        options.add_argument("--no-sandbox")

    if config.chrome_disable_dev_shm_usage:
        options.add_argument("--disable-dev-shm-usage")

    if config.chrome_proxy_server:
        options.add_argument(f"--proxy-server={config.chrome_proxy_server}")
        logging.info("Chrome proxy server is configured")

    if config.chrome_binary:
        options.binary_location = config.chrome_binary
        logging.info("Using Chrome binary: %s", config.chrome_binary)

    if config.chrome_user_data_dir:
        options.add_argument(f"--user-data-dir={config.chrome_user_data_dir}")
        logging.info("Using Chrome user data dir: %s", config.chrome_user_data_dir)
        if config.chrome_profile_directory:
            options.add_argument(f"--profile-directory={config.chrome_profile_directory}")
            logging.info("Using Chrome profile directory: %s", config.chrome_profile_directory)
    else:
        temp_profile_dir = tempfile.mkdtemp(prefix="xmonitor-chrome-")
        _TEMP_PROFILE_DIRS.append(temp_profile_dir)
        options.add_argument(f"--user-data-dir={temp_profile_dir}")
        logging.info("Using temporary Chrome profile: %s", temp_profile_dir)

    logging.info("Starting Chrome driver")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(config.page_load_timeout_seconds)
    logging.info("Chrome driver started successfully")
    return driver


def load_seen_ids(state_file: Path, keep_count: int) -> list[str]:
    if not state_file.exists():
        return []

    try:
        data = json.loads(state_file.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("Failed to load state file: %s", exc)
        return []

    if isinstance(data, dict):
        seen_ids = data.get("seen_ids")
        if isinstance(seen_ids, list):
            return [str(item) for item in seen_ids[:keep_count] if item]

        legacy_last_id = data.get("last_id")
        if legacy_last_id:
            return [str(legacy_last_id)]

    return []


def save_seen_ids(state_file: Path, seen_ids: list[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seen_ids": seen_ids,
        "updated_at": utc_now_iso(),
    }
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_seen_ids(current_ids: list[str], previous_ids: list[str], keep_count: int) -> list[str]:
    merged: list[str] = []
    for post_id in current_ids + previous_ids:
        if post_id and post_id not in merged:
            merged.append(post_id)
        if len(merged) >= keep_count:
            break
    return merged


def _diagnostic_name(reason: str) -> str:
    sanitized = "".join(ch if ch.isalnum() else "-" for ch in reason.lower()).strip("-")
    sanitized = "-".join(part for part in sanitized.split("-") if part)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}-{sanitized or 'browser-error'}"


def write_browser_diagnostics(driver: webdriver.Chrome, config: Config, reason: str) -> None:
    config.diagnostics_dir.mkdir(parents=True, exist_ok=True)
    base = config.diagnostics_dir / _diagnostic_name(reason)

    metadata = {
        "created_at": utc_now_iso(),
        "reason": reason,
        "target_username": config.target_username,
        "target_url": config.target_url,
        "current_url": "",
        "title": "",
        "page_source_length": 0,
        "html_truncated": False,
        "files": {},
    }

    try:
        metadata["current_url"] = driver.current_url
    except Exception as exc:
        metadata["current_url_error"] = str(exc)

    try:
        metadata["title"] = driver.title
    except Exception as exc:
        metadata["title_error"] = str(exc)

    try:
        html = driver.page_source or ""
        metadata["page_source_length"] = len(html)
        if config.diagnostics_html_max_chars and len(html) > config.diagnostics_html_max_chars:
            html = html[: config.diagnostics_html_max_chars]
            metadata["html_truncated"] = True
        html_path = base.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8", errors="ignore")
        metadata["files"]["html"] = str(html_path)
    except Exception as exc:
        metadata["html_error"] = str(exc)

    try:
        screenshot_path = base.with_suffix(".png")
        if driver.save_screenshot(str(screenshot_path)):
            metadata["files"]["screenshot"] = str(screenshot_path)
    except Exception as exc:
        metadata["screenshot_error"] = str(exc)

    metadata_path = base.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.warning("Saved browser diagnostics to %s", metadata_path)


def extract_recent_posts(driver: webdriver.Chrome, timeout_seconds: int, target_username: str, max_count: int) -> list[dict]:
    wait = WebDriverWait(driver, timeout_seconds)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]')))

    tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
    normalized_target = target_username.strip().lstrip("@").lower()
    collected: list[dict] = []
    seen_ids: set[str] = set()

    for tweet in tweets:
        links = tweet.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')

        post_url = ""
        post_id = ""
        matched_target = False

        for link in links:
            href = (link.get_attribute("href") or "").split("?", 1)[0]
            if "/status/" not in href or "x.com/" not in href:
                continue

            try:
                after_domain = href.split("x.com/", 1)[1]
                author_part = after_domain.split("/status/", 1)[0].strip("/").lower()
            except Exception:
                continue

            if author_part == normalized_target:
                post_url = href
                post_id = href.rsplit("/status/", maxsplit=1)[-1]
                matched_target = True
                break

        if not matched_target or not post_id or post_id in seen_ids:
            continue

        try:
            text_el = tweet.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
            text_content = text_el.text.strip()
        except NoSuchElementException:
            text_content = ""

        try:
            time_el = tweet.find_element(By.CSS_SELECTOR, "time")
            published_at = time_el.get_attribute("datetime") or ""
        except NoSuchElementException:
            published_at = ""

        collected.append(
            {
                "id": post_id,
                "url": post_url,
                "text": text_content,
                "time": published_at,
            }
        )
        seen_ids.add(post_id)

        if len(collected) >= max_count:
            break

    if not collected:
        raise NoSuchElementException(f"Unable to locate tweet/status cards authored by @{normalized_target}")

    return collected


def notify_console(post: dict) -> None:
    red = "\033[91m"
    yellow = "\033[93m"
    reset = "\033[0m"

    print(f"{red}[NEW UPDATE DETECTED]{reset}")
    print(f"{yellow}id:{reset} {post['id']}")
    print(f"{yellow}time:{reset} {post['time']}")
    print(f"{yellow}url:{reset} {post['url']}")
    print(f"{yellow}text:{reset} {post['text']}")


def notify_beep(enable_beep: bool) -> None:
    if not enable_beep:
        return

    try:
        if sys.platform.startswith("win"):
            import winsound

            winsound.Beep(1000, 400)
            winsound.Beep(1300, 350)
        else:
            print("\a", end="", flush=True)
    except Exception as exc:
        logging.warning("Beep failed: %s", exc)


def post_json(webhook: str, body: dict) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = url_request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with url_request.urlopen(req, timeout=10) as resp:
            response_text = resp.read().decode("utf-8", errors="ignore")
            logging.info("Webhook response: %s", response_text)
    except (url_error.URLError, TimeoutError) as exc:
        logging.warning("Webhook push failed: %s", exc)


def notify_webhooks(config: Config, post: dict) -> None:
    content = (
        "Probius X monitor detected a new post/reply\n"
        f"user: @{config.target_username}\n"
        f"id: {post['id']}\n"
        f"time: {post['time']}\n"
        f"url: {post['url']}\n"
        f"text: {post['text']}"
    )

    if config.feishu_webhook:
        post_json(
            config.feishu_webhook,
            {
                "msg_type": "text",
                "content": {"text": content},
            },
        )

    if config.dingtalk_webhook:
        post_json(
            config.dingtalk_webhook,
            {
                "msgtype": "text",
                "text": {"content": content},
            },
        )


def maybe_wait_for_login(config: Config, seen_ids: list[str]) -> None:
    if seen_ids:
        return

    if config.startup_login_wait_seconds > 0:
        logging.info(
            "Waiting %s seconds to allow manual login...",
            config.startup_login_wait_seconds,
        )
        time.sleep(config.startup_login_wait_seconds)


def monitor_loop(config: Config) -> None:
    driver: Optional[webdriver.Chrome] = None
    seen_ids = load_seen_ids(config.state_file, config.recent_post_count)
    last_diagnostics_at = 0.0

    while True:
        try:
            if driver is None:
                logging.info("Starting Chrome driver.")
                driver = build_driver(config)
                logging.info("Accessing target URL: %s", config.target_url)
                driver.get(config.target_url)
                logging.info("Page loaded successfully")
                maybe_wait_for_login(config, seen_ids)

            time.sleep(8)
            recent_posts = extract_recent_posts(
                driver,
                config.page_load_timeout_seconds,
                config.target_username,
                config.recent_post_count,
            )
            current_ids = [post["id"] for post in recent_posts]

            if not seen_ids:
                seen_ids = current_ids
                save_seen_ids(config.state_file, seen_ids)
                logging.info(
                    "Seeded seen_ids with first observed %s posts: %s",
                    len(seen_ids),
                    ", ".join(seen_ids),
                )
            else:
                new_posts = [post for post in reversed(recent_posts) if post["id"] not in seen_ids]

                if new_posts:
                    for post in new_posts:
                        notify_console(post)
                        notify_beep(config.enable_beep)
                        notify_webhooks(config, post)
                        logging.info("Detected new id %s", post["id"])

                    seen_ids = merge_seen_ids(current_ids, seen_ids, config.recent_post_count)
                    save_seen_ids(config.state_file, seen_ids)
                    logging.info("Updated seen_ids to: %s", ", ".join(seen_ids))
                else:
                    seen_ids = merge_seen_ids(current_ids, seen_ids, config.recent_post_count)
                    save_seen_ids(config.state_file, seen_ids)
                    logging.info(
                        "[monitoring] %s | status=ok | recent_ids=%s",
                        datetime.now().isoformat(),
                        ",".join(current_ids),
                    )

            sleep_for = config.check_interval_seconds + random.randint(
                -config.check_jitter_seconds,
                config.check_jitter_seconds,
            )
            sleep_for = max(5, sleep_for)
            logging.info("Sleeping for %s seconds.", sleep_for)
            time.sleep(sleep_for)

            try:
                driver.refresh()
                logging.info("Page refreshed successfully")
            except Exception as refresh_exc:
                logging.warning("Failed to refresh page: %s", refresh_exc)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None

        except (TimeoutException, NoSuchElementException, WebDriverException) as exc:
            logging.warning("Recoverable browser error: %s", exc)
            now = time.monotonic()
            should_write_diagnostics = (
                driver is not None
                and (
                    config.diagnostics_interval_seconds == 0
                    or now - last_diagnostics_at >= config.diagnostics_interval_seconds
                )
            )
            if should_write_diagnostics:
                try:
                    write_browser_diagnostics(driver, config, exc.__class__.__name__)
                    last_diagnostics_at = now
                except Exception as diagnostics_exc:
                    logging.warning("Failed to save browser diagnostics: %s", diagnostics_exc)
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
            time.sleep(5)
        except KeyboardInterrupt:
            logging.info("Stopped by user.")
            break
        except Exception as exc:
            logging.exception("Unexpected error: %s", exc)
            break

    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass
    _cleanup_temp_profiles()


def main() -> None:
    config = load_config()
    setup_logging(config.log_file)
    logging.info("Monitoring @%s on %s", config.target_username, config.target_url)
    monitor_loop(config)


if __name__ == "__main__":
    main()

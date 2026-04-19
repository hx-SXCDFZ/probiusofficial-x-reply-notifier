import json
import logging
import os
import sys
from pathlib import Path

from selenium.common.exceptions import WebDriverException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor import build_driver, load_config, setup_logging  # noqa: E402


COOKIE_FILE = Path(os.getenv("X_COOKIE_FILE", "/app/secrets/x-cookies.json"))


def normalize_cookie(cookie: dict) -> dict:
    allowed_keys = {"name", "value", "path", "domain", "secure", "httpOnly", "expiry", "sameSite"}
    normalized = {key: cookie[key] for key in allowed_keys if key in cookie and cookie[key] is not None}

    if "expiry" in normalized:
        normalized["expiry"] = int(normalized["expiry"])

    same_site = normalized.get("sameSite")
    if same_site not in {None, "Strict", "Lax", "None"}:
        normalized.pop("sameSite", None)

    return normalized


def load_cookies() -> list[dict]:
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"Cookie file not found: {COOKIE_FILE}")

    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and isinstance(data.get("value"), list):
        data = data["value"]

    if not isinstance(data, list):
        raise ValueError("Cookie file must contain a cookie list")

    return [normalize_cookie(cookie) for cookie in data if cookie.get("name") and cookie.get("value")]


def main() -> int:
    config = load_config()
    setup_logging(config.log_file)

    cookies = load_cookies()
    logging.info("Importing %s X cookies into Chrome profile", len(cookies))

    driver = build_driver(config)
    try:
        driver.get("https://x.com/")

        imported = 0
        skipped: list[str] = []
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
                imported += 1
            except WebDriverException as exc:
                skipped.append(cookie.get("name", "<unknown>"))
                logging.warning("Skipped cookie %s: %s", cookie.get("name", "<unknown>"), exc.msg)

        driver.get(config.target_url)
        logging.info("Opened target URL after cookie import: %s", driver.current_url)
        logging.info("Cookie import finished: imported=%s skipped=%s", imported, ",".join(skipped) or "none")
        return 0
    finally:
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())

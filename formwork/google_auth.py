import logging
import os
from pathlib import Path

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).parent.parent / "auth_state"
STATE_FILE = STATE_DIR / "google_state.json"


async def login_google(email: str, password: str) -> tuple:
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False)

    if STATE_FILE.exists():
        context = await browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.goto("https://accounts.google.com/")
        await page.wait_for_load_state("networkidle")

        if "signin" not in page.url:
            logger.info("使用已儲存的登入狀態")
            return p, browser, context

        logger.info("登入狀態已過期，重新登入...")
        await context.close()

    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    )
    page = await context.new_page()

    await page.goto("https://accounts.google.com/signin")
    await page.wait_for_load_state("networkidle")

    await page.wait_for_selector("#identifierId", timeout=10000)
    await page.fill("#identifierId", email)
    await page.click("#identifierNext")

    await page.wait_for_selector('input[type="password"]:visible', timeout=10000)
    await page.fill('input[type="password"]', password)
    await page.click("#passwordNext")

    await page.wait_for_url("**/myaccount.google.com/**", timeout=30000)
    logger.info("Google 登入成功")

    STATE_DIR.mkdir(exist_ok=True)
    await context.storage_state(path=str(STATE_FILE))
    logger.info("登入狀態已儲存")

    return p, browser, context

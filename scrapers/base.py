"""
爬虫基类：封装 Playwright 浏览器启动、页面创建、反爬策略等通用逻辑。
所有平台爬虫继承此基类。
"""

import logging
from playwright.async_api import async_playwright, Browser, Page
from utils import get_random_ua, random_delay, simulate_scroll
from config import PAGE_TIMEOUT, MIN_DELAY, MAX_DELAY

logger = logging.getLogger(__name__)


class BaseScraper:
    """爬虫基类，管理浏览器生命周期和通用反爬操作。"""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.browser: Browser = None
        self.playwright = None

    async def start_browser(self):
        """启动无头 Chromium 浏览器。"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        logger.info(f"[{self.platform_name}] 浏览器已启动")

    async def new_page(self) -> Page:
        """创建新页面并注入随机 User-Agent 和反检测脚本。"""
        context = await self.browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = await context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        # 注入反检测脚本：覆盖 navigator.webdriver 属性
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return page

    async def safe_goto(self, page: Page, url: str):
        """安全地导航到目标 URL，带随机延迟。"""
        await random_delay(MIN_DELAY, MAX_DELAY)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            logger.info(f"[{self.platform_name}] 已访问: {url}")
        except Exception as e:
            logger.warning(f"[{self.platform_name}] 访问失败 {url}: {e}")

    async def scroll_page(self, page: Page, times: int = 3):
        """模拟用户滚动页面。"""
        await simulate_scroll(page, times)

    async def close(self):
        """关闭浏览器和 Playwright 实例。"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info(f"[{self.platform_name}] 浏览器已关闭")

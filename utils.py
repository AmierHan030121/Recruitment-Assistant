"""
工具模块：提供爬虫运行的通用辅助功能。
- 随机延迟
- 模拟鼠标滚动
- 随机 User-Agent
"""

import random
import asyncio
from fake_useragent import UserAgent


def get_random_ua() -> str:
    """生成随机 User-Agent 字符串。"""
    try:
        ua = UserAgent()
        return ua.random
    except Exception:
        # 回退到一组预定义的 UA
        fallback = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(fallback)


async def random_delay(min_sec: int = 3, max_sec: int = 8):
    """在 min_sec ~ max_sec 秒之间随机等待，模拟人类操作节奏。"""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def simulate_scroll(page, scroll_times: int = 3):
    """
    模拟真实鼠标滚动行为：
    - 每次滚动距离随机（300~800 像素）
    - 每次滚动间隔随机（0.5~2 秒）
    """
    for _ in range(scroll_times):
        distance = random.randint(300, 800)
        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.5, 2.0))

"""
工具模块：提供爬虫运行和轻量文本处理的通用辅助功能。
"""

import asyncio
import random
import re
from datetime import datetime
from typing import Optional


STATIC_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
]


def choose_user_agent() -> str:
    return random.choice(STATIC_USER_AGENTS)


def get_random_ua() -> str:
    return choose_user_agent()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def timestamp_label(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return now.strftime("%Y%m%d_%H%M%S")


async def random_delay(min_sec: int = 1, max_sec: int = 2):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def simulate_scroll(page, scroll_times: int = 3):
    for _ in range(scroll_times):
        distance = random.randint(300, 800)
        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.5, 2.0))

"""
HTTP 抓取基础模块：提供默认请求头、Session 和重试请求函数。
"""

import time
from typing import Optional

import requests

from config import get_runtime_config
from utils import choose_user_agent


def build_default_headers() -> dict:
    return {
        "User-Agent": choose_user_agent(),
        "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(build_default_headers())
    return session


def request_text(session: requests.Session, url: str, *, timeout: Optional[int] = None) -> str:
    cfg = get_runtime_config()
    timeout = timeout or cfg.request_timeout
    last_error = None
    for attempt in range(cfg.max_retries):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == cfg.max_retries - 1:
                break
            time.sleep(0.5 * (attempt + 1))
    raise last_error

"""
智联招聘爬虫模块。
策略：按「城市 × 关键词 × 页码」抓取搜索页 HTML，
从页面内嵌的 __INITIAL_STATE__ 中直接解析职位列表和 JD。
"""

import asyncio
import json
import logging
import re
import urllib.parse
from typing import Callable, Dict, List, Optional

from bs4 import BeautifulSoup

from config import get_runtime_config
from scrapers.base import build_session, request_text

logger = logging.getLogger(__name__)


def _build_missing_state_context(html: str) -> str:
    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = ""
    if title_match:
        title = " ".join(title_match.group(1).split())

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    snippet = " ".join(text.split())[:120]

    parts = []
    if title:
        parts.append(f"title={title}")
    if snippet:
        parts.append(f"snippet={snippet}")
    return " | ".join(parts)


def _extract_json_object(payload: str) -> str:
    start = payload.find("{")
    if start < 0:
        raise ValueError("智联 __INITIAL_STATE__ 缺少 JSON 起始对象")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(payload)):
        char = payload[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return payload[start:index + 1]

    raise ValueError("智联 __INITIAL_STATE__ JSON 未正常闭合")


def is_zhilian_security_verification_page(html: str) -> bool:
    context = _build_missing_state_context(html).lower()
    markers = (
        "security verification",
        "tencent cloud edgeone",
        "protected by tencent cloud edgeone",
        "complete the challenge",
    )
    return any(marker in context for marker in markers)


class _ZhilianBrowserFetcher:
    def __init__(self, user_agent: str, timeout_seconds: int):
        self._user_agent = user_agent
        self._timeout_ms = timeout_seconds * 1000
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_page(self) -> None:
        if self._page is not None:
            return

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=self._user_agent,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        self._page = self._context.new_page()
        self._page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        self._page.goto(
            "https://www.zhaopin.com/",
            wait_until="domcontentloaded",
            timeout=self._timeout_ms,
        )
        self._page.wait_for_timeout(1500)

    def __call__(self, _session, url: str, **_kwargs) -> str:
        self._ensure_page()
        self._page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self._timeout_ms,
        )
        self._page.wait_for_timeout(1500)

        state_json = self._page.evaluate(
            "() => typeof window.__INITIAL_STATE__ === 'undefined' ? '' : JSON.stringify(window.__INITIAL_STATE__)"
        )
        if state_json:
            return f"<html><body><script>__INITIAL_STATE__={state_json}</script></body></html>"

        return self._page.content()

    def close(self) -> None:
        if self._page is not None:
            self._page.close()
            self._page = None
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None


def extract_initial_state(html: str) -> dict:
    marker = "__INITIAL_STATE__="
    start = html.find(marker)
    if start < 0:
        context = _build_missing_state_context(html)
        message = "未找到智联 __INITIAL_STATE__"
        if context:
            message = f"{message} | {context}"
        raise ValueError(message)
    after = html[start + len(marker):]
    payload = _extract_json_object(after)
    return json.loads(payload)


def parse_zhilian_positions(state: dict, city_name: str, keyword: str) -> list[dict]:
    jobs = []
    for item in state.get("positionList", []):
        desc = (
            item.get("jobDetailData", {})
            .get("position", {})
            .get("desc", {})
            .get("description", "")
        )
        jobs.append({
            "岗位名称": item.get("name", "").strip(),
            "公司名称": item.get("companyName", "").strip(),
            "薪资": item.get("salary60", "").strip() or "面议",
            "工作地点": item.get("workCity", "").strip() or city_name,
            "岗位描述": desc.strip(),
            "岗位类型": "实习",
            "来源平台": "智联招聘",
            "原始ID": item.get("number", "").strip(),
            "原始URL": item.get("positionURL", "").strip(),
            "抓取关键词": keyword,
            "抓取城市": city_name,
            "发布时间": item.get("publishTime", "").strip(),
        })
    return jobs


def parse_zhilian_job_cards(html: str, city_name: str, keyword: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for item in soup.select("div.joblist-box__item"):
        link = item.select_one("a.jobinfo__name[href*='jobdetail']")
        if not link:
            continue

        company_link = item.select_one("a[title][href*='companydetail']")
        salary_node = item.select_one(".jobinfo__salary")
        location_span = item.select_one(".jobinfo__other-info-item span")
        location_node = location_span or item.select_one(".jobinfo__other-info-item")

        url = link.get("href", "").strip()
        id_match = re.search(r"/jobdetail/([^./?]+)\.htm", url)

        jobs.append({
            "岗位名称": link.get_text(strip=True),
            "公司名称": (company_link.get("title") if company_link else "") or (
                company_link.get_text(strip=True) if company_link else ""
            ),
            "薪资": salary_node.get_text(strip=True) if salary_node else "面议",
            "工作地点": location_node.get_text(strip=True) if location_node else city_name,
            "岗位描述": "",
            "岗位类型": "实习",
            "来源平台": "智联招聘",
            "原始ID": id_match.group(1) if id_match else "",
            "原始URL": url,
            "抓取关键词": keyword,
            "抓取城市": city_name,
            "发布时间": "",
        })

    return jobs


def build_zhilian_page_queue() -> list[dict]:
    cfg = get_runtime_config()
    return [dict(item) for item in cfg.zhilian_page_plan]


def collect_zhilian_jobs(
    fetch_html: Callable = request_text,
    fetch_browser_html: Optional[Callable] = None,
    target_pool: int = 700,
    stop_requested: Callable[[], bool] = lambda: False,
) -> List[Dict]:
    cfg = get_runtime_config()
    session = build_session()
    results: List[Dict] = []
    seen_ids = set()
    browser_fetcher = None

    try:
        for item in build_zhilian_page_queue():
            if stop_requested() or len(results) >= target_pool:
                break

            max_pages = item["max_pages"]
            encoded_keyword = urllib.parse.quote(item["keyword"])

            for page in range(1, max_pages + 1):
                if stop_requested() or len(results) >= target_pool:
                    break

                url = (
                    f"https://www.zhaopin.com/sou/?"
                    f"jl={item['city_code']}&kw={encoded_keyword}&p={page}&et=4"
                )
                logger.info(
                    f"[智联招聘] [{item['city']}] [{item['keyword']}] "
                    f"第 {page}/{max_pages} 页..."
                )

                html = fetch_html(session, url)
                page_count = max_pages
                try:
                    state = extract_initial_state(html)
                    jobs = parse_zhilian_positions(
                        state,
                        city_name=item["city"],
                        keyword=item["keyword"],
                    )
                    page_count = int(state.get("pages", 1) or 1)
                except ValueError as exc:
                    logger.warning(
                        f"[智联招聘] 页面缺少嵌入状态，回退 HTML 卡片解析: {exc}"
                    )
                    jobs = parse_zhilian_job_cards(
                        html,
                        city_name=item["city"],
                        keyword=item["keyword"],
                    )

                    if not jobs and is_zhilian_security_verification_page(html):
                        logger.warning(
                            f"[智联招聘] 搜索页疑似风控验证，尝试浏览器兜底: "
                            f"city={item['city']} keyword={item['keyword']} page={page}"
                        )
                        if fetch_browser_html is None:
                            browser_fetcher = browser_fetcher or _ZhilianBrowserFetcher(
                                user_agent=session.headers.get("User-Agent", ""),
                                timeout_seconds=cfg.request_timeout,
                            )
                            fetch_browser_html = browser_fetcher

                        try:
                            browser_html = fetch_browser_html(session, url)
                        except Exception as browser_exc:
                            logger.error(
                                f"[智联招聘] 浏览器兜底失败: city={item['city']} "
                                f"keyword={item['keyword']} page={page} error={browser_exc}"
                            )
                            continue

                        try:
                            state = extract_initial_state(browser_html)
                            jobs = parse_zhilian_positions(
                                state,
                                city_name=item["city"],
                                keyword=item["keyword"],
                            )
                        except ValueError as browser_exc:
                            logger.warning(
                                f"[智联招聘] 浏览器页仍缺少嵌入状态，回退 HTML 卡片解析: "
                                f"{browser_exc}"
                            )
                            jobs = parse_zhilian_job_cards(
                                browser_html,
                                city_name=item["city"],
                                keyword=item["keyword"],
                            )

                    if not jobs:
                        logger.error(
                            f"[智联招聘] HTML 卡片解析也未获取到职位: city={item['city']} "
                            f"keyword={item['keyword']} page={page}"
                        )
                        continue

                for job in jobs:
                    original_id = job.get("原始ID", "")
                    if not original_id or original_id in seen_ids:
                        continue
                    seen_ids.add(original_id)
                    results.append(job)
                    if len(results) >= target_pool:
                        break

                if page >= page_count:
                    break
    finally:
        if browser_fetcher is not None:
            browser_fetcher.close()

    return results


async def scrape_zhilian() -> List[Dict]:
    import main as _main

    return await asyncio.to_thread(
        collect_zhilian_jobs,
        request_text,
        None,
        700,
        lambda: _main.shutdown_requested,
    )

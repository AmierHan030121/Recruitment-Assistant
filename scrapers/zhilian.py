"""
智联招聘爬虫模块。
策略：按「城市 × 关键词 × 页码」抓取搜索页 HTML，
从页面内嵌的 __INITIAL_STATE__ 中直接解析职位列表和 JD。
"""

import asyncio
import json
import logging
import urllib.parse
from typing import Callable, Dict, List

from config import get_runtime_config
from scrapers.base import build_session, request_text

logger = logging.getLogger(__name__)


def extract_initial_state(html: str) -> dict:
    marker = "__INITIAL_STATE__="
    start = html.find(marker)
    if start < 0:
        raise ValueError("未找到智联 __INITIAL_STATE__")
    after = html[start + len(marker):]
    end = after.find("</script>")
    if end < 0:
        raise ValueError("智联 __INITIAL_STATE__ 缺少结束标签")
    payload = after[:end].strip()
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


def build_zhilian_page_queue() -> list[dict]:
    cfg = get_runtime_config()
    return [dict(item) for item in cfg.zhilian_page_plan]


def collect_zhilian_jobs(
    fetch_html: Callable = request_text,
    target_pool: int = 700,
    stop_requested: Callable[[], bool] = lambda: False,
) -> List[Dict]:
    session = build_session()
    results: List[Dict] = []
    seen_ids = set()

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
            state = extract_initial_state(html)
            jobs = parse_zhilian_positions(
                state,
                city_name=item["city"],
                keyword=item["keyword"],
            )

            for job in jobs:
                original_id = job.get("原始ID", "")
                if not original_id or original_id in seen_ids:
                    continue
                seen_ids.add(original_id)
                results.append(job)
                if len(results) >= target_pool:
                    break

            if page >= state.get("pages", 1):
                break

    return results


async def scrape_zhilian() -> List[Dict]:
    import main as _main

    return await asyncio.to_thread(
        collect_zhilian_jobs,
        request_text,
        700,
        lambda: _main.shutdown_requested,
    )

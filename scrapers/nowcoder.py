"""
牛客网爬虫模块。
策略：按查询词组合抓取搜索页，再按需抓取详情页，作为补量源使用。
"""

import asyncio
import logging
import urllib.parse
from typing import Callable, Dict, List

from bs4 import BeautifulSoup

from config import get_runtime_config
from scrapers.base import build_session, request_text

logger = logging.getLogger(__name__)

ROLE_FAMILY_TERMS = (
    "数据分析",
    "商业分析",
    "经营分析",
    "数据运营",
    "数据产品分析",
    "用户研究",
    "数据治理",
    "市场分析",
    "行业研究",
    "商业数据分析",
    "产品运营",
)


def parse_nowcoder_search_results(html: str, target_city: str, keyword: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for link in soup.select("a[href*='/jobs/detail/']"):
        text = " ".join(link.get_text("\n", strip=True).split())
        if target_city not in text:
            continue
        if "实习" not in text:
            continue
        if not any(term in text for term in ROLE_FAMILY_TERMS):
            continue
        lines = [line.strip() for line in link.get_text("\n", strip=True).splitlines() if line.strip()]
        href = link["href"]
        detail_url = href if href.startswith("http") else f"https://www.nowcoder.com{href}"
        jobs.append({
            "岗位名称": lines[0],
            "薪资": lines[1] if len(lines) > 1 else "面议",
            "工作地点": target_city,
            "原始URL": detail_url,
            "抓取关键词": keyword,
            "抓取城市": target_city,
        })
    return jobs


def parse_nowcoder_job_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    company = next((line for line in lines if "有限公司" in line), "")
    city = next((line for line in lines if line in {"杭州", "上海", "南京"}), "")
    salary = next((line for line in lines if "元/天" in line or line == "面议"), "面议")
    description = text[text.index("岗位职责"):] if "岗位职责" in text else text
    return {
        "岗位名称": soup.find("h1").get_text(strip=True),
        "公司名称": company,
        "薪资": salary,
        "工作地点": city,
        "岗位描述": description,
        "岗位类型": "实习",
        "来源平台": "牛客网",
    }


def build_nowcoder_queries() -> list[dict]:
    return list(get_runtime_config().nowcoder_query_plan)


def collect_nowcoder_jobs(
    fetch_html: Callable = request_text,
    needed_count: int = 150,
    stop_requested: Callable[[], bool] = lambda: False,
) -> List[Dict]:
    session = build_session()
    results: List[Dict] = []
    seen_urls = set()

    for item in build_nowcoder_queries():
        if stop_requested() or len(results) >= needed_count:
            break

        encoded_query = urllib.parse.quote(item["query"])
        search_url = f"https://www.nowcoder.com/search/job?query={encoded_query}&type=job"
        logger.info(f"[牛客网] [{item['city']}] [{item['query']}] 搜索中...")
        search_html = fetch_html(session, search_url)
        cards = parse_nowcoder_search_results(
            search_html,
            target_city=item["city"],
            keyword=item["query"],
        )

        for card in cards:
            if stop_requested() or len(results) >= needed_count:
                break
            detail_url = card["原始URL"]
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            detail_html = fetch_html(session, detail_url)
            detail = parse_nowcoder_job_detail(detail_html)
            detail["原始URL"] = detail_url
            detail["抓取关键词"] = item["query"]
            detail["抓取城市"] = item["city"]
            detail["原始ID"] = detail_url.rstrip("/").split("/")[-1]
            results.append(detail)

    return results


async def scrape_nowcoder() -> List[Dict]:
    import main as _main

    return await asyncio.to_thread(
        collect_nowcoder_jobs,
        request_text,
        150,
        lambda: _main.shutdown_requested,
    )

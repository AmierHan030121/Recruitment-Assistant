"""
智联招聘爬虫模块。
策略：按「城市 × 页码」纯 URL 驱动，仅抓取实习岗位。
- URL 格式: sou.zhaopin.com/?jl={city_code}&kw={keyword}&p={page}&et=4
- 城市编码: 杭州=653, 南京=635, 上海=538
- 每个城市最多抓取 5 页
- 收到 SIGTERM 时安全退出并返回已抓取数据。
"""

import asyncio
import logging
import urllib.parse
from typing import List, Dict

from playwright.async_api import async_playwright
from config import (
    SEARCH_KEYWORD, ZHILIAN_JOB_TYPES, ZHILIAN_CITY_CODES,
    MIN_DELAY, MAX_DELAY,
    ZHILIAN_MULTI_PAGE_CITIES, ZHILIAN_MAX_PAGES,
)
from utils import random_delay

logger = logging.getLogger(__name__)


async def _fetch_jd_zhilian(page, detail_url: str) -> str:
    """访问智联招聘详情页并提取完整岗位描述。"""
    try:
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)

        try:
            await page.wait_for_selector(
                ".describtion, .describtion__detail-content, .job-description, "
                ".pos-ul, .responsibility, [class*='describe'], [class*='detail']",
                timeout=10000,
            )
        except Exception:
            await asyncio.sleep(2)

        parts = []
        for selector in (
            ".describtion .describtion__detail-content",
            ".describtion",
            ".job-description",
            ".pos-ul",
            ".responsibility",
            ".describe__content",
            ".job-detail-content",
        ):
            el = await page.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) > 20:
                    parts.append(text)

        if parts:
            return "\n".join(parts)

        text = await page.evaluate(
            """() => {
                const sels = [
                    '.describtion', '[class*="describe"]', '[class*="detail-content"]',
                    '[class*="responsibility"]', '.pos-ul'
                ];
                const texts = [];
                for (const s of sels) {
                    document.querySelectorAll(s).forEach(e => {
                        const t = e.innerText.trim();
                        if (t.length > 20) texts.push(t);
                    });
                }
                return [...new Set(texts)].join('\\n');
            }"""
        )
        if text and len(text.strip()) > 20:
            return text.strip()

        body = await page.inner_text("body")
        for kw in ("岗位职责", "职位描述", "工作内容", "任职要求", "职位要求"):
            idx = body.find(kw)
            if idx >= 0:
                return body[idx : idx + 2000].strip()

        return ""
    except Exception as e:
        logger.debug(f"[智联招聘] 详情页获取失败 {detail_url}: {e}")
        return ""


async def scrape_zhilian() -> List[Dict]:
    """按「城市 × 职位类型 × 页码」纯 URL 参数驱动抓取智联招聘。"""
    # 导入放在函数内以避免循环引用
    import main as _main

    results: List[Dict] = []
    kw_encoded = urllib.parse.quote(SEARCH_KEYWORD)
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )

            list_page = await context.new_page()
            detail_page = await context.new_page()

            await list_page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            await detail_page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )

            # 先访问主站建立 Session
            logger.info("[智联招聘] 访问主站获取 Session...")
            await list_page.goto(
                "https://www.zhaopin.com/",
                wait_until="domcontentloaded", timeout=30000,
            )
            await asyncio.sleep(2)

            for city, city_code in ZHILIAN_CITY_CODES.items():
                if _main.shutdown_requested:
                    logger.warning("[智联招聘] 收到终止信号，停止抓取")
                    break

                max_pages = (
                    ZHILIAN_MAX_PAGES
                    if city in ZHILIAN_MULTI_PAGE_CITIES
                    else 1
                )

                for job_type, et_value in ZHILIAN_JOB_TYPES.items():
                    if _main.shutdown_requested:
                        break

                    for page_num in range(1, max_pages + 1):
                        if _main.shutdown_requested:
                            break

                        # 纯 URL 参数：jl=城市编码 kw=关键词 p=页码 et=职位类型
                        page_url = (
                            f"https://sou.zhaopin.com/?"
                            f"jl={city_code}&kw={kw_encoded}"
                            f"&p={page_num}&et={et_value}"
                        )
                        logger.info(
                            f"[智联招聘] [{city}] [{job_type}] "
                            f"第 {page_num}/{max_pages} 页..."
                        )

                        await list_page.goto(
                            page_url,
                            wait_until="domcontentloaded", timeout=30000,
                        )
                        await asyncio.sleep(2)

                        # 等待卡片
                        try:
                            await list_page.wait_for_selector(
                                ".joblist-box__item", timeout=15000,
                            )
                        except Exception:
                            logger.info(
                                f"[智联招聘] [{city}] [{job_type}] "
                                f"第 {page_num} 页无职位卡片，停止翻页"
                            )
                            break

                        cards = await list_page.query_selector_all(
                            ".joblist-box__item"
                        )
                        if not cards:
                            logger.info(
                                f"[智联招聘] [{city}] [{job_type}] "
                                f"第 {page_num} 页无结果，停止翻页"
                            )
                            break

                        for i, card in enumerate(cards):
                            try:
                                name_el = await card.query_selector(
                                    "a.jobinfo__name"
                                )
                                job_name = (
                                    (await name_el.inner_text()).strip()
                                    if name_el else ""
                                )
                                detail_href = (
                                    (await name_el.get_attribute("href"))
                                    if name_el else ""
                                )

                                salary_el = await card.query_selector(
                                    "p.jobinfo__salary"
                                )
                                salary = (
                                    (await salary_el.inner_text()).strip()
                                    if salary_el else "面议"
                                )

                                comp_el = await card.query_selector(
                                    "a.companyinfo__name"
                                )
                                company = (
                                    (await comp_el.inner_text()).strip()
                                    if comp_el else ""
                                )

                                city_el = await card.query_selector(
                                    ".jobinfo__other-info-item span"
                                )
                                job_city = (
                                    (await city_el.inner_text()).strip()
                                    if city_el else city
                                )

                                jd = ""
                                if detail_href:
                                    detail_url = (
                                        detail_href
                                        if detail_href.startswith("http")
                                        else f"https:{detail_href}"
                                    )
                                    logger.info(
                                        f"[智联招聘] [{city}] [{job_type}] "
                                        f"p{page_num} 第 {i + 1}/{len(cards)} "
                                        f"条详情..."
                                    )
                                    jd = await _fetch_jd_zhilian(
                                        detail_page, detail_url,
                                    )
                                    await random_delay(1, 2)

                                if job_name:
                                    results.append({
                                        "岗位名称": job_name,
                                        "公司名称": company,
                                        "薪资": salary,
                                        "工作地点": job_city,
                                        "岗位描述": jd,
                                        "岗位类型": job_type,
                                        "来源平台": "智联招聘",
                                    })
                            except Exception as e:
                                logger.debug(
                                    f"[智联招聘] 解析单条岗位失败: {e}"
                                )
                                continue

                        logger.info(
                            f"[智联招聘] [{city}] [{job_type}] "
                            f"p{page_num} 解析 {len(cards)} 条"
                        )
                        await random_delay(MIN_DELAY, MAX_DELAY)

            await browser.close()
            browser = None

    except BaseException as e:
        logger.error(f"[智联招聘] 爬虫中断: {e}（已抓 {len(results)} 条，仍将提交）")
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    logger.info(
        f"[智联招聘] 共抓取 {len(results)} 条岗位"
        f"（{len(ZHILIAN_CITY_CODES)} 个城市 × "
        f"{len(ZHILIAN_JOB_TYPES)} 种类型）"
    )
    return results

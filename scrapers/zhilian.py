"""
智联招聘爬虫模块。
策略：按「城市 × 职位类型」逐一搜索。
- 北京/上海：每个组合抓取最多 5 页
- 其余城市：每个组合仅抓取第 1 页
城市通过 URL 参数 jl={城市名} 指定。
职位类型通过页面「职位类型」筛选下拉框逐个选择（全职 / 兼职/临时 / 实习 / 校园）。
逐条访问详情页获取完整岗位描述。
"""

import asyncio
import logging
import urllib.parse
from typing import List, Dict

from playwright.async_api import async_playwright
from config import (
    SEARCH_KEYWORD, TARGET_CITIES, ZHILIAN_JOB_TYPES,
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


async def _click_job_type_filter(page, job_type: str) -> bool:
    """
    点击「职位类型」筛选下拉框并选择指定类型。
    返回 True 表示成功选中，False 表示失败。
    """
    try:
        # 查找"职位类型"筛选按钮
        filter_btn = page.locator(
            "[class*='filter'] >> text=职位类型, "
            "[class*='condition'] >> text=职位类型, "
            "[class*='screen'] >> text=职位类型"
        ).first
        await filter_btn.click(timeout=5000)
        await asyncio.sleep(0.5)

        # 在下拉面板中选择目标类型
        option = page.locator(
            f"[class*='filter'] >> text='{job_type}', "
            f"[class*='option'] >> text='{job_type}'"
        ).first
        await option.click(timeout=5000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.debug(f"[智联招聘] 点击职位类型[{job_type}]失败: {e}")
        return False


async def _clear_filters(page):
    """清除当前所有筛选条件（点击"清空筛选条件"）。"""
    try:
        clear_btn = page.locator("text=清空筛选条件").first
        if await clear_btn.is_visible(timeout=2000):
            await clear_btn.click()
            await asyncio.sleep(1)
    except Exception:
        pass


async def scrape_zhilian() -> List[Dict]:
    """按「城市 × 职位类型」逐一抓取智联招聘的数据分析岗位。
    北京/上海抓取最多 ZHILIAN_MAX_PAGES 页，其余城市仅第 1 页。
    """
    results: List[Dict] = []
    kw_encoded = urllib.parse.quote(SEARCH_KEYWORD)

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

            for city in TARGET_CITIES:
                city_encoded = urllib.parse.quote(city)
                max_pages = (
                    ZHILIAN_MAX_PAGES
                    if city in ZHILIAN_MULTI_PAGE_CITIES
                    else 1
                )

                for job_type in ZHILIAN_JOB_TYPES:
                    for page_num in range(1, max_pages + 1):
                        page_url = (
                            f"https://sou.zhaopin.com/?"
                            f"jl={city_encoded}&kw={kw_encoded}&p={page_num}"
                        )
                        logger.info(
                            f"[智联招聘] [{city}] [{job_type}] "
                            f"第 {page_num}/{max_pages} 页..."
                        )

                        # 每次重新加载页面（确保筛选状态干净）
                        await list_page.goto(
                            page_url,
                            wait_until="domcontentloaded", timeout=30000,
                        )
                        await asyncio.sleep(2)

                        # 尝试选择职位类型
                        filter_ok = await _click_job_type_filter(
                            list_page, job_type,
                        )
                        if not filter_ok:
                            logger.debug(
                                f"[智联招聘] [{city}] "
                                f"职位类型[{job_type}]筛选跳过"
                            )

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
                            await random_delay(1, 2)
                            break  # 无结果则停止该类型的后续页

                        cards = await list_page.query_selector_all(
                            ".joblist-box__item"
                        )
                        if not cards:
                            logger.info(
                                f"[智联招聘] [{city}] [{job_type}] "
                                f"第 {page_num} 页无结果，停止翻页"
                            )
                            await random_delay(1, 2)
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
                                    await random_delay(1, 3)

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

    except Exception as e:
        logger.error(f"[智联招聘] 爬虫异常: {e}")

    logger.info(
        f"[智联招聘] 共抓取 {len(results)} 条岗位"
        f"（{len(TARGET_CITIES)} 个城市 × "
        f"{len(ZHILIAN_JOB_TYPES)} 种类型）"
    )
    return results

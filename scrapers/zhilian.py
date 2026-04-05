"""
智联招聘爬虫模块。
策略：Playwright 访问 sou.zhaopin.com，等待职位卡片加载后直接 CSS 选择器提取。
无需拦截 AJAX（数据由客户端 JS 渲染至 DOM）。
"""

import asyncio
import logging
import urllib.parse
from typing import List, Dict
from playwright.async_api import async_playwright
from config import SEARCH_KEYWORD, MAX_PAGES, MIN_DELAY, MAX_DELAY
from utils import random_delay

logger = logging.getLogger(__name__)

_CITY_CODE = "530"   # 全国不限


async def scrape_zhilian() -> List[Dict]:
    """
    抓取智联招聘的数据分析岗位。
    使用 Playwright 直接从 DOM 中提取职位卡片数据。
    """
    results = []
    kw_encoded = urllib.parse.quote(SEARCH_KEYWORD)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
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
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )

            # 先访问主站建立 Session
            logger.info("[智联招聘] 访问主站获取 Session...")
            await page.goto("https://www.zhaopin.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            for page_num in range(1, MAX_PAGES + 1):
                search_url = (
                    f"https://sou.zhaopin.com/?"
                    f"jl={_CITY_CODE}&kw={kw_encoded}&p={page_num}"
                )
                logger.info(f"[智联招聘] 正在抓取第 {page_num} 页...")
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                # 等待职位卡片渲染完毕
                try:
                    await page.wait_for_selector(".joblist-box__item", timeout=20000)
                except Exception:
                    logger.warning(f"[智联招聘] 第 {page_num} 页未找到职位卡片，停止抓取")
                    break

                cards = await page.query_selector_all(".joblist-box__item")
                if not cards:
                    logger.info(f"[智联招聘] 第 {page_num} 页无数据，停止翻页")
                    break

                for card in cards:
                    try:
                        # 岗位名称
                        name_el = await card.query_selector("a.jobinfo__name")
                        job_name = (await name_el.inner_text()).strip() if name_el else ""

                        # 薪资
                        salary_el = await card.query_selector("p.jobinfo__salary")
                        salary = (await salary_el.inner_text()).strip() if salary_el else "面议"

                        # 公司名称
                        comp_el = await card.query_selector("a.companyinfo__name")
                        company = (await comp_el.inner_text()).strip() if comp_el else ""

                        # 工作地点（第一个 .jobinfo__other-info-item 内的 span）
                        city_el = await card.query_selector(".jobinfo__other-info-item span")
                        city = (await city_el.inner_text()).strip() if city_el else ""

                        # 岗位标签（作为描述信息）
                        tag_els = await card.query_selector_all(".jobinfo__tag .joblist-box__item-tag")
                        tags = [await t.inner_text() for t in tag_els]
                        desc = ", ".join(tags)

                        # 岗位类型
                        full_text = job_name + " " + desc
                        if "实习" in full_text:
                            job_type = "实习"
                        elif "兼职" in full_text:
                            job_type = "兼职"
                        else:
                            job_type = "全职"

                        if job_name:
                            results.append({
                                "岗位名称": job_name,
                                "公司名称": company,
                                "薪资": salary,
                                "工作地点": city,
                                "岗位描述": desc,
                                "岗位类型": job_type,
                                "来源平台": "智联招聘",
                            })
                    except Exception as e:
                        logger.debug(f"[智联招聘] 解析单条岗位失败: {e}")
                        continue

                logger.info(f"[智联招聘] 第 {page_num} 页解析 {len(cards)} 条")
                await random_delay(MIN_DELAY, MAX_DELAY)

            await browser.close()

    except Exception as e:
        logger.error(f"[智联招聘] 爬虫异常: {e}")

    logger.info(f"[智联招聘] 共抓取 {len(results)} 条岗位")
    return results

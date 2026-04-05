"""
智联招聘爬虫模块。
策略：按城市逐一搜索，每个城市仅抓取第 1 页，逐个访问详情页获取完整岗位描述。
URL 格式：sou.zhaopin.com/?jl={城市名}&kw=数据分析&p=1
"""

import asyncio
import logging
import urllib.parse
from typing import List, Dict
from playwright.async_api import async_playwright
from config import SEARCH_KEYWORD, TARGET_CITIES, MIN_DELAY, MAX_DELAY
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
    """按城市逐一抓取智联招聘的数据分析岗位（每城市第 1 页）。"""
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
            await list_page.goto("https://www.zhaopin.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            for city in TARGET_CITIES:
                city_encoded = urllib.parse.quote(city)
                search_url = (
                    f"https://sou.zhaopin.com/?"
                    f"jl={city_encoded}&kw={kw_encoded}&p=1"
                )
                logger.info(f"[智联招聘] 正在抓取 [{city}] ...")
                await list_page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                try:
                    await list_page.wait_for_selector(".joblist-box__item", timeout=20000)
                except Exception:
                    logger.info(f"[智联招聘] [{city}] 未找到职位卡片，跳过")
                    await random_delay(1, 3)
                    continue

                cards = await list_page.query_selector_all(".joblist-box__item")
                if not cards:
                    logger.info(f"[智联招聘] [{city}] 无结果")
                    await random_delay(1, 3)
                    continue

                for i, card in enumerate(cards):
                    try:
                        name_el = await card.query_selector("a.jobinfo__name")
                        job_name = (await name_el.inner_text()).strip() if name_el else ""
                        detail_href = (await name_el.get_attribute("href")) if name_el else ""

                        salary_el = await card.query_selector("p.jobinfo__salary")
                        salary = (await salary_el.inner_text()).strip() if salary_el else "面议"

                        comp_el = await card.query_selector("a.companyinfo__name")
                        company = (await comp_el.inner_text()).strip() if comp_el else ""

                        city_el = await card.query_selector(".jobinfo__other-info-item span")
                        job_city = (await city_el.inner_text()).strip() if city_el else city

                        jd = ""
                        if detail_href:
                            detail_url = detail_href if detail_href.startswith("http") else f"https:{detail_href}"
                            logger.info(
                                f"[智联招聘] [{city}] "
                                f"获取第 {i + 1}/{len(cards)} 条详情..."
                            )
                            jd = await _fetch_jd_zhilian(detail_page, detail_url)
                            await random_delay(1, 3)

                        full_text = job_name + " " + jd
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
                                "工作地点": job_city,
                                "岗位描述": jd,
                                "岗位类型": job_type,
                                "来源平台": "智联招聘",
                            })
                    except Exception as e:
                        logger.debug(f"[智联招聘] 解析单条岗位失败: {e}")
                        continue

                logger.info(f"[智联招聘] [{city}] 解析 {len(cards)} 条")
                await random_delay(MIN_DELAY, MAX_DELAY)

            await browser.close()

    except Exception as e:
        logger.error(f"[智联招聘] 爬虫异常: {e}")

    logger.info(f"[智联招聘] 共抓取 {len(results)} 条岗位（{len(TARGET_CITIES)} 个城市）")
    return results

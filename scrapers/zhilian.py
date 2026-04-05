"""
智联招聘爬虫模块。
策略：Playwright 访问 sou.zhaopin.com，等待职位卡片加载后提取基本信息，
再逐个访问详情页获取完整岗位描述。
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


async def _fetch_jd_zhilian(page, detail_url: str) -> str:
    """访问智联招聘详情页并提取完整岗位描述。"""
    try:
        await page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)

        # 等待 JD 内容出现
        try:
            await page.wait_for_selector(
                ".describtion, .describtion__detail-content, .job-description, "
                ".pos-ul, .responsibility, [class*='describe'], [class*='detail']",
                timeout=10000,
            )
        except Exception:
            await asyncio.sleep(2)

        # 依次尝试多个已知选择器
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

        # JS 广泛查找
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

        # 从 body 中截取 JD 段落
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
    """
    抓取智联招聘的数据分析岗位，包括详情页 JD。
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

            for page_num in range(1, MAX_PAGES + 1):
                search_url = (
                    f"https://sou.zhaopin.com/?"
                    f"jl={_CITY_CODE}&kw={kw_encoded}&p={page_num}"
                )
                logger.info(f"[智联招聘] 正在抓取第 {page_num} 页...")
                await list_page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                # 等待职位卡片渲染完毕
                try:
                    await list_page.wait_for_selector(".joblist-box__item", timeout=20000)
                except Exception:
                    logger.warning(f"[智联招聘] 第 {page_num} 页未找到职位卡片，停止抓取")
                    break

                cards = await list_page.query_selector_all(".joblist-box__item")
                if not cards:
                    logger.info(f"[智联招聘] 第 {page_num} 页无数据，停止翻页")
                    break

                for i, card in enumerate(cards):
                    try:
                        # 岗位名称 + 详情页链接
                        name_el = await card.query_selector("a.jobinfo__name")
                        job_name = (await name_el.inner_text()).strip() if name_el else ""
                        detail_href = (await name_el.get_attribute("href")) if name_el else ""

                        # 薪资
                        salary_el = await card.query_selector("p.jobinfo__salary")
                        salary = (await salary_el.inner_text()).strip() if salary_el else "面议"

                        # 公司名称
                        comp_el = await card.query_selector("a.companyinfo__name")
                        company = (await comp_el.inner_text()).strip() if comp_el else ""

                        # 工作地点
                        city_el = await card.query_selector(".jobinfo__other-info-item span")
                        city = (await city_el.inner_text()).strip() if city_el else ""

                        # 访问详情页获取完整 JD
                        jd = ""
                        if detail_href:
                            detail_url = detail_href if detail_href.startswith("http") else f"https:{detail_href}"
                            logger.info(
                                f"[智联招聘] 第 {page_num} 页: "
                                f"获取第 {i + 1}/{len(cards)} 条详情..."
                            )
                            jd = await _fetch_jd_zhilian(detail_page, detail_url)
                            await random_delay(1, 3)

                        # 岗位类型
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
                                "工作地点": city,
                                "岗位描述": jd,
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

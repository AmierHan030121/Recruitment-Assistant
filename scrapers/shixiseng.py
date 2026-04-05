"""
实习僧爬虫模块。
目标页面：https://www.shixiseng.com/interns?keyword=数据分析&type=intern
抓取字段：公司名称、岗位名称、薪资、工作地点、岗位描述、岗位类型

列表页 DOM（移动端渲染）:
  .list-row > .lauch_box > .list-item[data-intern-id]
    .right
      .flex-row.first .title     <- 岗位名称
      .flex-row.first .salary    <- 薪资
      .flex-line .text (第一个)   <- 工作城市
      .company                   <- 公司名称

详情页（/intern/{data-intern-id}）中提取完整岗位描述。
使用桌面 UA 访问详情页以获取完整渲染的 JD 内容。
"""

import asyncio
import logging
import re
import urllib.parse
from typing import List, Dict
from playwright.async_api import async_playwright
from config import SEARCH_KEYWORD, MAX_PAGES, MIN_DELAY, MAX_DELAY
from utils import random_delay, simulate_scroll

logger = logging.getLogger(__name__)

# 岗位名称必须包含以下关键词之一才视为"数据分析"相关
_RELEVANT_RE = re.compile(
    r"数据分析|数据运营|数据挖掘|数据开发|数据产品|数据工程|BI|"
    r"商业分析|业务分析|经营分析|数据治理|数据中台|数据仓库|"
    r"数据科学|大数据|数据管理|数据策略|数据平台|数据研发",
    re.IGNORECASE,
)

# 实习僧列表页固定使用手机端 UA（网站始终渲染移动端布局）
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_jd_shixiseng(page, intern_id: str) -> str:
    """访问实习僧详情页提取岗位描述。"""
    url = f"https://www.shixiseng.com/intern/{intern_id}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)

        # 等待内容渲染
        try:
            await page.wait_for_function(
                """() => {
                    const el = document.querySelector(
                        '.job_detail, .intern_detail, .description, '
                        + '.desc-content, .job_good_list, [class*="desc"], [class*="require"]'
                    );
                    return el && el.innerText.trim().length > 10;
                }""",
                timeout=10000,
            )
        except Exception:
            # 滚动触发懒加载
            await simulate_scroll(page, scroll_times=3)
            await asyncio.sleep(2)

        # 依次尝试多个选择器
        parts = []
        for selector in (
            ".job_detail",
            ".intern_detail",
            ".description_card",
            ".desc-content",
            ".description",
            ".require_card",
            ".require",
            ".job_good_list",
        ):
            el = await page.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) > 10:
                    parts.append(text)

        if parts:
            return "\n".join(parts)

        # 用 JS 广泛查找
        text = await page.evaluate(
            """() => {
                const sels = [
                    '.job_detail', '.intern_detail', '.detail-content',
                    '[class*="desc"]', '[class*="require"]', '[class*="detail"]'
                ];
                const texts = [];
                for (const s of sels) {
                    document.querySelectorAll(s).forEach(e => {
                        const t = e.innerText.trim();
                        if (t.length > 15) texts.push(t);
                    });
                }
                return [...new Set(texts)].join('\\n');
            }"""
        )
        if text and len(text.strip()) > 20:
            return text.strip()

        # 最终兜底：从 body 搜索 JD 关键段落
        body = await page.inner_text("body")
        for kw in ("岗位职责", "职位介绍", "工作内容", "任职要求"):
            idx = body.find(kw)
            if idx >= 0:
                return body[idx : idx + 1500].strip()

        return ""
    except Exception as e:
        logger.debug(f"[实习僧] 详情页获取失败 {url}: {e}")
        return ""


async def scrape_shixiseng() -> List[Dict]:
    """抓取实习僧的数据分析岗位，包括详情页 JD。"""
    results = []
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

            # 移动端上下文 —— 列表页
            mobile_ctx = await browser.new_context(
                user_agent=_MOBILE_UA,
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                locale="zh-CN",
            )
            await mobile_ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            list_page = await mobile_ctx.new_page()

            # 桌面端上下文 —— 详情页（内容更完整）
            desktop_ctx = await browser.new_context(
                user_agent=_DESKTOP_UA,
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            await desktop_ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            detail_page = await desktop_ctx.new_page()

            for page_num in range(1, MAX_PAGES + 1):
                url = (
                    f"https://www.shixiseng.com/interns?"
                    f"keyword={kw_encoded}&type=intern&page={page_num}"
                )
                logger.info(f"[实习僧] 正在抓取第 {page_num} 页...")

                await random_delay(MIN_DELAY, MAX_DELAY)
                try:
                    await list_page.goto(
                        url, wait_until="domcontentloaded", timeout=30000
                    )
                except Exception as e:
                    logger.warning(f"[实习僧] 页面加载异常: {e}")
                    continue

                try:
                    await list_page.wait_for_selector(
                        ".list-item[data-intern-id]", timeout=15000
                    )
                except Exception:
                    logger.warning(f"[实习僧] 第 {page_num} 页未找到岗位卡片")
                    break

                await simulate_scroll(list_page, scroll_times=4)

                cards = await list_page.query_selector_all(
                    ".list-item[data-intern-id]"
                )
                if not cards:
                    logger.warning(f"[实习僧] 第 {page_num} 页 cards 为空")
                    break

                for i, card in enumerate(cards):
                    try:
                        job = {}

                        name_el = await card.query_selector(".right .title")
                        job["岗位名称"] = (
                            (await name_el.inner_text()).strip() if name_el else ""
                        )

                        # 提前过滤：岗位名称不相关则跳过（不再浪费时间访问详情页）
                        if not job["岗位名称"] or not _RELEVANT_RE.search(job["岗位名称"]):
                            if job["岗位名称"]:
                                logger.debug(f"[实习僧] 跳过无关岗位: {job['岗位名称']}")
                            continue

                        salary_el = await card.query_selector(".right .salary")
                        job["薪资"] = (
                            (await salary_el.inner_text()).strip()
                            if salary_el
                            else "面议"
                        )

                        city_el = await card.query_selector(
                            ".right .flex-line .text"
                        )
                        job["工作地点"] = (
                            (await city_el.inner_text()).strip() if city_el else ""
                        )

                        company_el = await card.query_selector(".right .company")
                        job["公司名称"] = (
                            (await company_el.inner_text()).strip()
                            if company_el
                            else ""
                        )

                        # 获取详情页 JD
                        intern_id = await card.get_attribute("data-intern-id")
                        if intern_id:
                            logger.info(
                                f"[实习僧] 第 {page_num} 页: "
                                f"获取第 {i + 1}/{len(cards)} 条详情..."
                            )
                            job["岗位描述"] = await _fetch_jd_shixiseng(
                                detail_page, intern_id
                            )
                            await random_delay(1, 3)
                        else:
                            job["岗位描述"] = ""

                        job["岗位类型"] = "实习"
                        job["来源平台"] = "实习僧"

                        if job["公司名称"]:
                            results.append(job)
                    except Exception as e:
                        logger.debug(f"[实习僧] 解析单条岗位失败: {e}")
                        continue

                logger.info(
                    f"[实习僧] 第 {page_num} 页解析 {len(cards)} 张卡片"
                )

            await browser.close()

    except Exception as e:
        logger.error(f"[实习僧] 爬虫异常: {e}")

    logger.info(f"[实习僧] 共抓取 {len(results)} 条岗位")
    return results

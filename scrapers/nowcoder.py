"""
牛客网爬虫模块。
目标页面：https://www.nowcoder.com/search?type=job&query=数据分析
抓取字段：公司名称、岗位名称、薪资、工作地点、岗位描述、岗位类型

列表页 DOM 结构：
  .job-card-item
    .job-message-boxs
      .job-name           <- 岗位名称（可能带 "校招 | " 等前缀）
      .job-salary         <- 薪资
      .job-info-item      <- 标签列表（前两项为平台标签，第三项起为城市/学历等）
    .company-message-box
      .company-name       <- 公司名称
    a[href*='jobs/detail'] <- 详情页链接

详情页（/jobs/detail/{id}）中提取完整岗位描述（JD）。
"""

import re
import asyncio
import logging
import urllib.parse
from typing import List, Dict
from scrapers.base import BaseScraper
from config import SEARCH_KEYWORD, MAX_PAGES
from utils import random_delay

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r'^(校招|实习|社招|急招|春招|秋招)\s*[|丨]\s*', re.IGNORECASE)

# 非城市关键词，用于从 .job-info-item 列表中筛选出真实城市
_NON_CITY_KW = (
    "学业", "在线", "简历", "处理", "HR", "活跃", "牛友", "收藏",
    "届", "本科", "硕士", "博士", "大专", "/周", "个月", "天/周",
)


def _clean_job_name(raw: str) -> str:
    """去除 "校招 | "、"实习 | " 等前缀。"""
    return _PREFIX_RE.sub('', raw).strip()


def _pick_city(info_texts: list) -> str:
    """从 .job-info-item 文本列表中智能提取城市名。"""
    for text in info_texts:
        if any(kw in text for kw in _NON_CITY_KW):
            continue
        # 跳过纯英文技能标签（如 "SQL", "Python"）
        if re.fullmatch(r'[A-Za-z0-9+#./ ]+', text):
            continue
        return text
    return info_texts[2] if len(info_texts) > 2 else ""


async def _fetch_jd(page, url: str) -> str:
    """访问牛客详情页提取岗位描述。"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)

        # 方案 1：Element UI 卡片中查找含 JD 关键词的区域
        cards = await page.query_selector_all(".el-card__body")
        for card in cards:
            text = (await card.inner_text()).strip()
            if len(text) > 30 and any(
                kw in text for kw in ("岗位职责", "任职要求", "岗位要求", "工作内容", "职位描述")
            ):
                return text

        # 方案 2：常见详情页选择器
        for selector in (".recruit-text", ".position-detail", ".nc-detail-content",
                         ".card-container", ".detail-main"):
            el = await page.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 30:
                    return text

        # 方案 3：从 body 文本中截取 JD 段落
        body_text = await page.inner_text("body")
        for keyword in ("岗位职责", "职位描述", "工作内容", "任职要求"):
            idx = body_text.find(keyword)
            if idx >= 0:
                return body_text[idx:idx + 1500].strip()

        return ""
    except Exception as e:
        logger.debug(f"[牛客网] 详情页获取失败 {url}: {e}")
        return ""


async def scrape_nowcoder() -> List[Dict]:
    """抓取牛客网的数据分析岗位，包括详情页 JD。"""
    scraper = BaseScraper("牛客网")
    results = []
    kw_encoded = urllib.parse.quote(SEARCH_KEYWORD)

    try:
        await scraper.start_browser()
        list_page = await scraper.new_page()
        detail_page = await scraper.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = (
                f"https://www.nowcoder.com/search?type=job"
                f"&searchType=&query={kw_encoded}&page={page_num}"
            )
            await scraper.safe_goto(list_page, url)
            await scraper.scroll_page(list_page, times=4)

            logger.info(f"[牛客网] 正在抓取第 {page_num} 页...")

            try:
                await list_page.wait_for_selector(".job-card-item", timeout=15000)
            except Exception:
                logger.warning("[牛客网] 未找到 .job-card-item")

            cards = await list_page.query_selector_all(".job-card-item")
            if not cards:
                cards = await list_page.query_selector_all(
                    ".recruit-job-item, [class*='jobItem']"
                )
            if not cards:
                logger.warning(f"[牛客网] 第 {page_num} 页未找到卡片")
                break

            for i, card in enumerate(cards):
                try:
                    job = {}

                    # 岗位名称
                    name_el = await card.query_selector(".job-name")
                    raw_name = (await name_el.inner_text()).strip() if name_el else ""
                    job["岗位名称"] = _clean_job_name(raw_name)

                    # 薪资
                    salary_el = await card.query_selector(".job-salary")
                    job["薪资"] = (await salary_el.inner_text()).strip() if salary_el else "面议"

                    # 工作地点（智能提取）
                    info_items = await card.query_selector_all(".job-info-item")
                    info_texts = []
                    for item in info_items:
                        info_texts.append((await item.inner_text()).strip())
                    job["工作地点"] = _pick_city(info_texts)

                    # 公司名称
                    company_el = await card.query_selector(".company-name")
                    job["公司名称"] = (
                        (await company_el.inner_text()).strip() if company_el else ""
                    )

                    # 详情页 → 岗位描述
                    link_el = await card.query_selector("a[href*='jobs/detail']")
                    if link_el:
                        href = await link_el.get_attribute("href")
                        if href:
                            detail_url = (
                                href
                                if href.startswith("http")
                                else f"https://www.nowcoder.com{href}"
                            )
                            logger.info(
                                f"[牛客网] 第 {page_num} 页: "
                                f"获取第 {i + 1}/{len(cards)} 条详情..."
                            )
                            job["岗位描述"] = await _fetch_jd(detail_page, detail_url)
                            await random_delay(1, 3)
                    else:
                        job["岗位描述"] = ""

                    # 岗位类型
                    if "实习" in raw_name:
                        job["岗位类型"] = "实习"
                    elif "兼职" in raw_name:
                        job["岗位类型"] = "兼职"
                    else:
                        job["岗位类型"] = "全职"

                    job["来源平台"] = "牛客网"

                    if job["岗位名称"] and job["公司名称"]:
                        results.append(job)
                except Exception as e:
                    logger.debug(f"[牛客网] 解析单条岗位失败: {e}")
                    continue

            logger.info(f"[牛客网] 第 {page_num} 页解析 {len(cards)} 张卡片")
            await random_delay()

        logger.info(f"[牛客网] 共抓取 {len(results)} 条岗位")

    except Exception as e:
        logger.error(f"[牛客网] 爬虫异常: {e}")
    finally:
        await scraper.close()

    return results

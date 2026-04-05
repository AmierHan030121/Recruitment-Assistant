"""
牛客网爬虫模块。
策略：按「职位类型 × 城市」逐一搜索，每个组合仅抓取第 1 页。
职位类型：实习 / 校招 / 社招（分别点击对应标签页）。
城市筛选：通过页面城市级联筛选器逐个勾选（一个城市一搜索，保证页面结果充分）。

DOM 结构（搜索页 /search?type=job）：
  div.filter-recruit-type  <- 职位类型标签（实习 / 校招 / 社招）
  div.city-cascader        <- 城市筛选器触发按钮
  .nc-city-cascader-popover
    div.cascader-item      <- 省份列表（浙江省 / 广东省 / 北京 / 上海 …）
    label.el-checkbox.cascader-item-content <- 城市复选框

列表页卡片：
  .job-card-item
    .job-name / .job-salary / .job-info-item / .company-name
    a[href*='jobs/detail']  <- 详情页链接

详情页（/jobs/detail/{id}）提取完整 JD。
"""

import re
import asyncio
import logging
import urllib.parse
from typing import List, Dict

from scrapers.base import BaseScraper
from config import (
    SEARCH_KEYWORD, PROVINCE_CITIES, NOWCODER_JOB_TYPES,
)
from utils import random_delay

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r'^(校招|实习|社招|急招|春招|秋招)\s*[|丨]\s*', re.IGNORECASE)

_NON_CITY_KW = (
    "学业", "在线", "简历", "处理", "HR", "活跃", "牛友", "收藏",
    "届", "本科", "硕士", "博士", "大专", "/周", "个月", "天/周",
)


def _clean_job_name(raw: str) -> str:
    return _PREFIX_RE.sub('', raw).strip()


def _pick_city(info_texts: list) -> str:
    for text in info_texts:
        if any(kw in text for kw in _NON_CITY_KW):
            continue
        if re.fullmatch(r'[A-Za-z0-9+#./ ]+', text):
            continue
        return text
    return info_texts[2] if len(info_texts) > 2 else ""


# --------------- 页面交互辅助 ---------------

async def _hide_login_dialog(page):
    """隐藏牛客登录弹窗（阻止 UI 交互）。"""
    await page.evaluate("""() => {
        document.querySelectorAll(
            '.login-dialog, .el-dialog__wrapper.login-dialog'
        ).forEach(e => e.style.display = 'none');
    }""")


async def _click_job_type_tab(page, job_type: str):
    """点击职位类型标签（实习 / 校招 / 社招）。"""
    tab = page.locator(f"div.filter-recruit-type:has-text('{job_type}')")
    await tab.click(force=True)
    await asyncio.sleep(2)


async def _open_cascader(page):
    """打开城市级联筛选器弹出层。"""
    trigger = page.locator("div.city-cascader")
    await trigger.click(force=True)
    await asyncio.sleep(0.5)


async def _select_city(page, province: str, city: str):
    """
    在城市级联筛选器中勾选指定城市：
    1. 打开级联器
    2. 滚动到省份并点击
    3. 点击城市复选框
    4. 关闭级联器，等待结果刷新
    """
    await _open_cascader(page)

    # 点击省份
    prov_item = page.locator(
        f".nc-city-cascader-popover div.cascader-item:has-text('{province}')"
    )
    try:
        await prov_item.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    await prov_item.click(force=True)
    await asyncio.sleep(0.3)

    # 点击城市复选框
    city_cb = page.locator(
        f".nc-city-cascader-popover label.cascader-item-content:has-text('{city}')"
    )
    await city_cb.first.click(force=True)
    await asyncio.sleep(0.3)

    # 关闭级联器（点击页面空白处）
    await page.mouse.click(10, 10)
    await asyncio.sleep(2)


async def _deselect_city(page, province: str, city: str):
    """取消城市勾选（再点一次复选框取消）。"""
    await _open_cascader(page)

    prov_item = page.locator(
        f".nc-city-cascader-popover div.cascader-item:has-text('{province}')"
    )
    try:
        await prov_item.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    await prov_item.click(force=True)
    await asyncio.sleep(0.3)

    city_cb = page.locator(
        f".nc-city-cascader-popover label.cascader-item-content:has-text('{city}')"
    )
    await city_cb.first.click(force=True)
    await asyncio.sleep(0.3)

    await page.mouse.click(10, 10)
    await asyncio.sleep(1)


# --------------- 详情页 JD ---------------

async def _fetch_jd(page, url: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)

        cards = await page.query_selector_all(".el-card__body")
        for card in cards:
            text = (await card.inner_text()).strip()
            if len(text) > 30 and any(
                kw in text for kw in ("岗位职责", "任职要求", "岗位要求", "工作内容", "职位描述")
            ):
                return text

        for selector in (".recruit-text", ".position-detail", ".nc-detail-content",
                         ".card-container", ".detail-main"):
            el = await page.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 30:
                    return text

        body_text = await page.inner_text("body")
        for keyword in ("岗位职责", "职位描述", "工作内容", "任职要求"):
            idx = body_text.find(keyword)
            if idx >= 0:
                return body_text[idx:idx + 1500].strip()

        return ""
    except Exception as e:
        logger.debug(f"[牛客网] 详情页获取失败 {url}: {e}")
        return ""


# --------------- 主入口 ---------------

async def scrape_nowcoder() -> List[Dict]:
    """按「职位类型 × 城市」逐一抓取牛客网的数据分析岗位。"""
    scraper = BaseScraper("牛客网")
    results: List[Dict] = []
    kw_encoded = urllib.parse.quote(SEARCH_KEYWORD)
    search_url = (
        f"https://www.nowcoder.com/search?type=job"
        f"&query={kw_encoded}&page=1"
    )

    try:
        await scraper.start_browser()
        list_page = await scraper.new_page()
        detail_page = await scraper.new_page()

        for job_type in NOWCODER_JOB_TYPES:
            logger.info(f"[牛客网] ===== 开始抓取【{job_type}】类型 =====")

            # 每个职位类型重新加载搜索页（ reset 所有筛选状态）
            await scraper.safe_goto(list_page, search_url)
            await scraper.scroll_page(list_page, times=2)
            await asyncio.sleep(1)
            await _hide_login_dialog(list_page)

            # 点击职位类型标签
            try:
                await _click_job_type_tab(list_page, job_type)
            except Exception as e:
                logger.warning(f"[牛客网] 点击 [{job_type}] 标签失败: {e}")
                continue

            for province, cities in PROVINCE_CITIES.items():
                for city in cities:
                    logger.info(f"[牛客网] [{job_type}] [{city}] 选择城市...")
                    try:
                        await _select_city(list_page, province, city)
                    except Exception as e:
                        logger.warning(f"[牛客网] [{job_type}] [{city}] 选择城市失败: {e}")
                        # 尝试恢复：重新加载
                        try:
                            await scraper.safe_goto(list_page, search_url)
                            await asyncio.sleep(1)
                            await _hide_login_dialog(list_page)
                            await _click_job_type_tab(list_page, job_type)
                        except Exception:
                            pass
                        continue

                    # 等待岗位卡片
                    try:
                        await list_page.wait_for_selector(
                            ".job-card-item", timeout=8000
                        )
                    except Exception:
                        logger.info(f"[牛客网] [{job_type}] [{city}] 无结果")
                        try:
                            await _deselect_city(list_page, province, city)
                        except Exception:
                            pass
                        await random_delay(1, 2)
                        continue

                    cards = await list_page.query_selector_all(".job-card-item")
                    if not cards:
                        logger.info(f"[牛客网] [{job_type}] [{city}] 无岗位卡片")
                        try:
                            await _deselect_city(list_page, province, city)
                        except Exception:
                            pass
                        await random_delay(1, 2)
                        continue

                    # 解析卡片
                    for i, card in enumerate(cards):
                        try:
                            job = {}

                            name_el = await card.query_selector(".job-name")
                            raw_name = (await name_el.inner_text()).strip() if name_el else ""
                            job["岗位名称"] = _clean_job_name(raw_name)

                            salary_el = await card.query_selector(".job-salary")
                            job["薪资"] = (await salary_el.inner_text()).strip() if salary_el else "面议"

                            info_items = await card.query_selector_all(".job-info-item")
                            info_texts = [
                                (await item.inner_text()).strip() for item in info_items
                            ]
                            job["工作地点"] = _pick_city(info_texts)

                            company_el = await card.query_selector(".company-name")
                            job["公司名称"] = (
                                (await company_el.inner_text()).strip() if company_el else ""
                            )

                            # 详情页 JD
                            link_el = await card.query_selector("a[href*='jobs/detail']")
                            if link_el:
                                href = await link_el.get_attribute("href")
                                if href:
                                    detail_url = (
                                        href if href.startswith("http")
                                        else f"https://www.nowcoder.com{href}"
                                    )
                                    logger.info(
                                        f"[牛客网] [{job_type}] [{city}] "
                                        f"第 {i + 1}/{len(cards)} 条详情..."
                                    )
                                    job["岗位描述"] = await _fetch_jd(detail_page, detail_url)
                                    await random_delay(1, 3)
                            else:
                                job["岗位描述"] = ""

                            # 岗位类型：直接使用当前 tab 类型
                            job["岗位类型"] = job_type if job_type != "社招" else "全职"
                            if job_type == "校招":
                                job["岗位类型"] = "全职"

                            job["来源平台"] = "牛客网"

                            if job["岗位名称"] and job["公司名称"]:
                                results.append(job)
                        except Exception as e:
                            logger.debug(f"[牛客网] 解析单条岗位失败: {e}")
                            continue

                    logger.info(
                        f"[牛客网] [{job_type}] [{city}] 解析 {len(cards)} 张卡片"
                    )

                    # 取消城市勾选，准备下一个城市
                    try:
                        await _deselect_city(list_page, province, city)
                    except Exception:
                        # 如果取消失败，下一轮会重新加载
                        logger.debug(f"[牛客网] [{city}] 取消勾选失败，将在下轮重载")

                    await random_delay(2, 4)

        logger.info(
            f"[牛客网] 共抓取 {len(results)} 条岗位"
            f"（{len(NOWCODER_JOB_TYPES)} 种类型 × "
            f"{len([c for cs in PROVINCE_CITIES.values() for c in cs])} 个城市）"
        )

    except Exception as e:
        logger.error(f"[牛客网] 爬虫异常: {e}")
    finally:
        await scraper.close()

    return results

"""
牛客网爬虫模块。
策略：仅抓取「实习」类型，按城市逐个搜索，每个组合仅抓取第 1 页。
城市筛选：通过页面城市级联筛选器逐个勾选（杭州/南京/上海）。

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
    "投递", "刚刚", "有人", "浏览", "沟通", "更新", "发布",
)


def _clean_job_name(raw: str) -> str:
    return _PREFIX_RE.sub('', raw).strip()


def _pick_city(info_texts: list) -> str:
    for text in info_texts:
        if any(kw in text for kw in _NON_CITY_KW):
            continue
        if re.fullmatch(r'[A-Za-z0-9+#./ ]+', text):
            continue
        # 城市名称一般 2-6 个字符
        if len(text) > 6:
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
    """
    精确点击职位类型标签（实习）。
    使用 JavaScript 遍历 DOM，找到文本节点内容严格等于 job_type 的叶子元素并点击，
    避免 Playwright :has-text() 匹配到包含全部标签文字的外层容器。
    """
    clicked = await page.evaluate("""
        (jobType) => {
            // 找所有"文本节点内容严格等于 jobType"的元素
            const candidates = [];
            document.querySelectorAll('*').forEach(el => {
                const directText = Array.from(el.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE)
                    .map(n => n.textContent.trim())
                    .join('');
                if (directText === jobType) candidates.push(el);
            });
            // 优先点击 class 里含有 recruit / filter / tab 的元素
            for (const el of candidates) {
                const cls = (el.className || '').toLowerCase();
                if (cls.includes('recruit') || cls.includes('filter') || cls.includes('tab')) {
                    el.click();
                    return 'class:' + el.className;
                }
            }
            // 兜底：点击第一个候选
            if (candidates.length > 0) {
                candidates[0].click();
                return 'fallback:' + candidates[0].tagName;
            }
            return null;
        }
    """, job_type)

    if not clicked:
        raise Exception(f"未找到职位类型标签: {job_type}")
    logger.debug(f"[牛客网] 点击标签 [{job_type}] → {clicked}")
    await asyncio.sleep(2)


async def _open_cascader(page):
    """打开城市级联筛选器弹出层，并等待内容可见。"""
    trigger = page.locator("div.city-cascader")
    await trigger.click(force=True)
    # 等待弹层真正出现（最多 5 秒）
    try:
        await page.wait_for_selector(
            ".nc-city-cascader-popover", state="visible", timeout=5000
        )
    except Exception:
        await asyncio.sleep(1)


async def _js_click_text(page, container_sel: str, text: str, exact: bool = True) -> bool:
    """
    在 container_sel 范围内，用 JS 找到整个 innerText 严格等于 text 的元素并点击。
    返回 True 表示点击成功。
    """
    return await page.evaluate("""
        ([sel, txt, exact]) => {
            const container = document.querySelector(sel);
            if (!container) return false;
            const walker = document.createTreeWalker(
                container, NodeFilter.SHOW_ELEMENT
            );
            while (walker.nextNode()) {
                const el = walker.currentNode;
                const t = (el.innerText || '').trim();
                if (exact ? t === txt : t.includes(txt)) {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """, [container_sel, text, exact])


async def _select_city(page, province: str, city: str):
    """
    在城市级联筛选器中勾选指定城市。
    直辖市（如上海）：名称直接出现在左侧列表，无需展开省级。
    普通省份：先点省份展开右侧城市列表，再点城市复选框。
    全程用 JS 点击避免元素可见性报错。
    """
    await _open_cascader(page)
    POPOVER = ".nc-city-cascader-popover"

    # 直辖市：名称已在左侧列表中，直接点省级内容（即城名）
    # 普通省：先点省份展开
    ok = await _js_click_text(page, POPOVER, province, exact=True)
    if not ok:
        raise Exception(f"未找到省份项: {province}")
    await asyncio.sleep(0.5)

    # 直辖市情况下 province==city，左侧点击即展开右侧城区列表
    # 普通省展开后右侧出现城市复选框
    # 两种情况都用 JS 点击包含 city 文字的 label
    ok2 = await page.evaluate("""
        ([sel, city]) => {
            const container = document.querySelector(sel);
            if (!container) return false;
            // 找 label 或 span，内容严格等于 city
            for (const el of container.querySelectorAll(
                'label.cascader-item-content, span.cascader-item-content, label'
            )) {
                if ((el.innerText || '').trim() === city) {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """, [POPOVER, city])
    if not ok2:
        raise Exception(f"未找到城市复选框: {city}")
    await asyncio.sleep(0.3)

    # 关闭级联器（点击页面空白处）
    await page.mouse.click(10, 10)
    await asyncio.sleep(2)


async def _deselect_city(page, province: str, city: str):
    """取消城市勾选（再点一次复选框取消）。"""
    await _open_cascader(page)
    POPOVER = ".nc-city-cascader-popover"

    await _js_click_text(page, POPOVER, province, exact=True)
    await asyncio.sleep(0.5)

    await page.evaluate("""
        ([sel, city]) => {
            const container = document.querySelector(sel);
            if (!container) return;
            for (const el of container.querySelectorAll(
                'label.cascader-item-content, span.cascader-item-content, label'
            )) {
                if ((el.innerText || '').trim() === city) { el.click(); return; }
            }
        }
    """, [POPOVER, city])
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
    import main as _main

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
            if _main.shutdown_requested:
                logger.warning("[牛客网] 收到终止信号，停止抓取")
                break

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
                if _main.shutdown_requested:
                    break
                for city in cities:
                    if _main.shutdown_requested:
                        break
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

    except BaseException as e:
        # 捕获 asyncio.CancelledError（BaseException 子类）等所有异常
        # 记录日志后继续，将已抓取的数据 return 给上层
        logger.error(f"[牛客网] 爬虫中断: {e}（已抓 {len(results)} 条，仍将提交）")
    finally:
        await scraper.close()

    return results

"""
数据清洗模块：
1. 工作地点标准化到市级
2. 提取技术工具和业务关键词
3. 按原始 ID 和业务键去重
4. 按杭州优先的规则打分排序
5. 截断到目标条数并执行质量校验
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import BUSINESS_KEYWORDS, TECH_TOOLS, get_runtime_config

logger = logging.getLogger(__name__)

_MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}
_CITY_SEP_RE = re.compile(r"[-·•/\\|，,\s]+")
_CITY_SUFFIX_RE = re.compile(r"^(.{2,})(?:市|州)$")
_ROLE_FAMILY_TERMS = ("数据分析", "商业分析", "经营分析", "数据运营", "数据产品分析", "用户研究")


def normalize_city(raw_city: str) -> str:
    if not raw_city:
        return ""
    text = raw_city.strip()

    for municipality in _MUNICIPALITIES:
        if text.startswith(municipality):
            return municipality

    parts = _CITY_SEP_RE.split(text)
    for part in parts:
        part = part.strip()
        if not part or part.endswith("省"):
            continue
        if re.search(r"[区县镇乡]$", part) and len(part) <= 5:
            continue
        match = _CITY_SUFFIX_RE.match(part)
        if match:
            return match.group(1)
        if 2 <= len(part) <= 4 and not part.endswith("省"):
            return part

    first = parts[0].strip() if parts else text
    first = re.sub(r"[市区县]+$", "", first)
    return first if first else text


def extract_tech_tools(jd_text: str) -> str:
    if not jd_text:
        return ""
    found = []
    for tool in TECH_TOOLS:
        pattern = re.compile(re.escape(tool), re.IGNORECASE)
        if pattern.search(jd_text):
            found.append(tool)
    return ", ".join(dict.fromkeys(found))


def extract_business_keywords(jd_text: str) -> str:
    if not jd_text:
        return ""
    found = []
    for keyword in BUSINESS_KEYWORDS:
        if keyword.upper() in jd_text.upper():
            found.append(keyword)
    return ", ".join(dict.fromkeys(found))


def _build_business_dedup_key(row: pd.Series) -> str:
    return "_".join([
        str(row.get("公司名称", "")).strip(),
        str(row.get("岗位名称", "")).strip(),
        str(row.get("工作地点", "")).strip(),
    ])


def _score_row(row: pd.Series) -> int:
    score = 0
    title = str(row.get("岗位名称", ""))
    desc = str(row.get("岗位描述", ""))
    keyword = str(row.get("抓取关键词", ""))

    if any(term in title for term in _ROLE_FAMILY_TERMS):
        score += 50
    elif any(term in desc for term in _ROLE_FAMILY_TERMS):
        score += 20

    if "实习" in title or "实习" in str(row.get("岗位类型", "")):
        score += 20
    if len(desc) >= 80:
        score += 10

    city = str(row.get("工作地点", ""))
    if city == "杭州":
        score += 15
    elif city == "上海":
        score += 10
    elif city == "南京":
        score += 5

    if "数据分析" in keyword:
        score += 5

    return score


def clean_data(raw_jobs: List[Dict], target_count: Optional[int] = None) -> pd.DataFrame:
    cfg = get_runtime_config()
    target_count = target_count or cfg.target_final_count

    if not raw_jobs:
        logger.warning("原始数据为空，跳过清洗")
        return pd.DataFrame()

    df = pd.DataFrame(raw_jobs)
    df = df[df["岗位名称"].fillna("").str.strip().astype(bool)]
    df = df[df["公司名称"].fillna("").str.strip().astype(bool)]

    for col in ["薪资", "工作地点", "岗位描述", "岗位类型", "来源平台", "原始ID", "抓取关键词", "抓取城市", "发布时间"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    df["工作地点"] = df["工作地点"].apply(normalize_city)
    df["技术工具"] = df["岗位描述"].apply(extract_tech_tools)
    df["业务关键词"] = df["岗位描述"].apply(extract_business_keywords)
    df["业务去重键"] = df.apply(_build_business_dedup_key, axis=1)

    if "发布时间" in df.columns:
        df = df.sort_values(by=["发布时间"], ascending=False)

    if "原始ID" in df.columns:
        df = df.drop_duplicates(subset=["原始ID"], keep="first")
    df = df.drop_duplicates(subset=["业务去重键"], keep="first")

    df["排序分"] = df.apply(_score_row, axis=1)
    df = df.sort_values(by=["排序分", "发布时间"], ascending=[False, False]).reset_index(drop=True)

    company_counts = {}
    kept_rows = []
    for _, row in df.iterrows():
        company = row["公司名称"]
        company_counts.setdefault(company, 0)
        if company_counts[company] >= cfg.company_row_soft_cap:
            continue
        company_counts[company] += 1
        kept_rows.append(row)
        if len(kept_rows) >= target_count:
            break

    final_df = pd.DataFrame(kept_rows).reset_index(drop=True)
    logger.info(f"清洗完成，最终有效数据 {len(final_df)} 条")
    return final_df


def validate_final_dataset(df: pd.DataFrame, source_counts: Dict[str, int]) -> Tuple[bool, List[str]]:
    cfg = get_runtime_config()
    reasons: List[str] = []

    if len(df) < cfg.min_valid_result_count:
        reasons.append(f"最低有效数不足: {len(df)} < {cfg.min_valid_result_count}")

    if source_counts.get("智联招聘", 0) < cfg.min_zhilian_result_count:
        reasons.append(
            f"智联结果过低: {source_counts.get('智联招聘', 0)} < {cfg.min_zhilian_result_count}"
        )

    hangzhou_count = int((df["工作地点"] == "杭州").sum()) if not df.empty else 0
    if hangzhou_count < cfg.min_hangzhou_result_count:
        reasons.append(f"杭州结果过低: {hangzhou_count} < {cfg.min_hangzhou_result_count}")

    return len(reasons) == 0, reasons

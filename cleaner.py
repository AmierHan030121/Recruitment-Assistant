"""
数据清洗模块：
1. 从 JD 文本中提取技术工具和业务关键词
2. 工作地点标准化（只保留到市级）
3. 字段空值填充与去重
"""

import re
import logging
import pandas as pd
from typing import List, Dict
from config import TECH_TOOLS, BUSINESS_KEYWORDS, CITY_PROVINCE_MAP

logger = logging.getLogger(__name__)

# 直辖市列表
_MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}

# 分隔符：用于拆分 "广东-广州"、"上海·浦东" 等
_CITY_SEP_RE = re.compile(r'[-·•/\\|，,\s]+')

# 匹配 "xx市" 并提取市名
_CITY_SUFFIX_RE = re.compile(r'^(.{2,})(?:市|州)$')


def normalize_city(raw_city: str) -> str:
    """
    将工作地点标准化为市级名称。
    例：
      "北京市朝阳区" → "北京"
      "广东-广州-天河区" → "广州"
      "上海·浦东新区" → "上海"
      "杭州市" → "杭州"
      "深圳 南山区" → "深圳"
    """
    if not raw_city:
        return ""
    text = raw_city.strip()

    # 直辖市：只要出现就直接返回
    for m in _MUNICIPALITIES:
        if text.startswith(m):
            return m

    # 按分隔符拆分，逐段检查
    parts = _CITY_SEP_RE.split(text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 跳过省份级别（xx省）
        if part.endswith("省"):
            continue
        # 跳过区/县级
        if re.search(r'[区县镇乡]$', part) and len(part) <= 5:
            continue
        # "xx市" → "xx"
        m = _CITY_SUFFIX_RE.match(part)
        if m:
            return m.group(1)
        # 短名字且不是省/区，视为城市
        if 2 <= len(part) <= 4 and not part.endswith("省"):
            return part

    # 兜底：返回去掉"市/区"后缀的首段
    first = parts[0].strip() if parts else text
    first = re.sub(r'[市区县]+$', '', first)
    return first if first else text


def extract_tech_tools(jd_text: str) -> str:
    """从岗位描述中提取技术工具关键词。"""
    if not jd_text:
        return ""
    found = []
    for tool in TECH_TOOLS:
        pattern = re.compile(re.escape(tool), re.IGNORECASE)
        if pattern.search(jd_text):
            found.append(tool)
    return ", ".join(dict.fromkeys(found))


def extract_business_keywords(jd_text: str) -> str:
    """从岗位描述中提取业务关键词。"""
    if not jd_text:
        return ""
    found = []
    for kw in BUSINESS_KEYWORDS:
        if kw.upper() in jd_text.upper():
            found.append(kw)
    return ", ".join(dict.fromkeys(found))


def clean_data(raw_jobs: List[Dict]) -> pd.DataFrame:
    """
    对原始岗位数据进行全面清洗：
    1. 去除空岗位名/空公司名
    2. 工作地点标准化到市级
    3. 提取技术工具和业务关键词
    4. 填充空值
    5. 以"公司名+岗位名"去重
    """
    if not raw_jobs:
        logger.warning("原始数据为空，跳过清洗")
        return pd.DataFrame()

    df = pd.DataFrame(raw_jobs)

    # 去除岗位名或公司名为空的行
    df = df[df["岗位名称"].str.strip().astype(bool)]
    df = df[df["公司名称"].str.strip().astype(bool)]

    # 填充空值
    for col in ["薪资", "工作地点", "岗位描述", "岗位类型", "来源平台"]:
        if col in df.columns:
            df[col] = df[col].fillna("")

    # 工作地点标准化：先提取市级，再映射到省级（浙江/江苏/广东）
    df["工作地点"] = df["工作地点"].apply(normalize_city)
    df["工作地点"] = df["工作地点"].apply(
        lambda c: CITY_PROVINCE_MAP.get(c, c)
    )

    # 提取技术工具和业务关键词
    df["技术工具"] = df["岗位描述"].apply(extract_tech_tools)
    df["业务关键词"] = df["岗位描述"].apply(extract_business_keywords)

    # 以"公司名+岗位名"去重
    dedup_key = df["公司名称"].str.strip() + "_" + df["岗位名称"].str.strip()
    before = len(df)
    df = df.loc[~dedup_key.duplicated(keep="first")]
    after = len(df)
    if before > after:
        logger.info(f"数据去重: {before} -> {after} 条（移除 {before - after} 条重复）")

    df = df.reset_index(drop=True)
    logger.info(f"清洗完成，最终有效数据 {len(df)} 条")
    return df

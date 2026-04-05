"""
数据清洗模块：
1. 从 JD 文本中提取技术工具和业务关键词
2. 薪资字符串标准化（拆分为 salary_min / salary_max）
3. 字段空值填充与去重
"""

import re
import logging
import pandas as pd
from typing import List, Dict
from config import TECH_TOOLS, BUSINESS_KEYWORDS

logger = logging.getLogger(__name__)


def extract_tech_tools(jd_text: str) -> str:
    """
    从岗位描述中提取技术工具关键词。
    返回以逗号分隔的字符串，如 "SQL, Python, Tableau"。
    """
    if not jd_text:
        return ""
    found = []
    jd_upper = jd_text.upper()
    for tool in TECH_TOOLS:
        # 使用单词边界或中文前后匹配
        pattern = re.compile(re.escape(tool), re.IGNORECASE)
        if pattern.search(jd_text):
            found.append(tool)
    # 去重并保持原始顺序
    return ", ".join(dict.fromkeys(found))


def extract_business_keywords(jd_text: str) -> str:
    """
    从岗位描述中提取业务关键词。
    返回以逗号分隔的字符串，如 "留存分析, 漏斗模型, 用户画像"。
    """
    if not jd_text:
        return ""
    found = []
    for kw in BUSINESS_KEYWORDS:
        if kw.upper() in jd_text.upper():
            found.append(kw)
    return ", ".join(dict.fromkeys(found))


def normalize_salary(salary_str: str) -> Dict[str, str]:
    """
    将薪资字符串标准化为 salary_min、salary_max 和 salary_unit。
    
    支持的格式举例：
    - "15k-25k"           -> min=15000, max=25000, unit=月薪
    - "15K-25K·14薪"      -> min=15000, max=25000, unit=月薪
    - "8-12K/月"           -> min=8000, max=12000, unit=月薪
    - "200-300元/天"       -> min=200, max=300, unit=日薪
    - "面议" / ""          -> min="", max="", unit=""
    """
    result = {"salary_min": "", "salary_max": "", "salary_unit": "", "salary_raw": salary_str}

    if not salary_str or salary_str.strip() in ("面议", "待遇面议", "薪资面议"):
        return result

    text = salary_str.strip()
    text_upper = text.upper()

    # 先根据文本判断薪资单位
    if "天" in text or "日" in text:
        unit = "日薪"
    elif "年" in text:
        unit = "年薪"
    else:
        unit = "月薪"

    # 模式1：15K-25K 或 15k-25k（可能带 ·14薪）
    match = re.search(r"(\d+(?:\.\d+)?)\s*[Kk]\s*[-~至]\s*(\d+(?:\.\d+)?)\s*[Kk]", text_upper)
    if match:
        result["salary_min"] = str(int(float(match.group(1)) * 1000))
        result["salary_max"] = str(int(float(match.group(2)) * 1000))
        result["salary_unit"] = unit
        return result

    # 模式2：8-12K/月 或 8-12k
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-~至]\s*(\d+(?:\.\d+)?)\s*[Kk]", text_upper)
    if match:
        result["salary_min"] = str(int(float(match.group(1)) * 1000))
        result["salary_max"] = str(int(float(match.group(2)) * 1000))
        result["salary_unit"] = unit
        return result

    # 模式3：15000-25000（纯数字范围）
    match = re.search(r"(\d{3,})\s*[-~至]\s*(\d{3,})", text)
    if match:
        min_val = int(match.group(1))
        max_val = int(match.group(2))
        if min_val >= 100000 and "月" not in text:
            unit = "年薪"
        result["salary_min"] = str(min_val)
        result["salary_max"] = str(max_val)
        result["salary_unit"] = unit
        return result

    # 模式4：200-300元/天
    match = re.search(r"(\d+)\s*[-~至]\s*(\d+)\s*元", text)
    if match:
        result["salary_min"] = match.group(1)
        result["salary_max"] = match.group(2)
        result["salary_unit"] = unit
        return result

    return result


def clean_data(raw_jobs: List[Dict]) -> pd.DataFrame:
    """
    对原始岗位数据进行全面清洗：
    1. 去除空岗位名/空公司名
    2. 标准化薪资
    3. 提取技术工具和业务关键词
    4. 填充空值
    5. 以"公司名+岗位名"生成唯一键用于去重
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

    # 标准化薪资
    salary_info = df["薪资"].apply(normalize_salary)
    df["薪资下限"] = salary_info.apply(lambda x: x["salary_min"])
    df["薪资上限"] = salary_info.apply(lambda x: x["salary_max"])
    df["薪资单位"] = salary_info.apply(lambda x: x["salary_unit"])
    df["薪资原始"] = salary_info.apply(lambda x: x["salary_raw"])

    # 提取技术工具和业务关键词
    df["技术工具"] = df["岗位描述"].apply(extract_tech_tools)
    df["业务关键词"] = df["岗位描述"].apply(extract_business_keywords)

    # 生成去重键
    df["unique_key"] = df["公司名称"].str.strip() + "_" + df["岗位名称"].str.strip()

    # 按唯一键去重，保留第一条
    before = len(df)
    df = df.drop_duplicates(subset=["unique_key"], keep="first")
    after = len(df)
    if before > after:
        logger.info(f"数据去重: {before} -> {after} 条（移除 {before - after} 条重复）")

    df = df.reset_index(drop=True)
    logger.info(f"清洗完成，最终有效数据 {len(df)} 条")
    return df

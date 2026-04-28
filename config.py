"""
配置模块：管理运行时配置、关键词、城市优先级和飞书凭据。
敏感信息仅从环境变量读取，不再回退到硬编码默认值。
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FeishuConfig:
    app_id: Optional[str]
    app_secret: Optional[str]
    app_token: Optional[str]
    table_id: Optional[str]


@dataclass(frozen=True)
class RuntimeConfig:
    feishu: FeishuConfig
    target_final_count: int
    min_valid_result_count: int
    min_zhilian_result_count: int
    min_hangzhou_result_count: int
    company_row_soft_cap: int
    request_timeout: int
    max_retries: int
    target_cities_priority: list[str]
    keyword_groups: dict[str, list[str]]
    zhilian_page_plan: list[dict]
    nowcoder_query_plan: list[dict]


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        feishu=FeishuConfig(
            app_id=os.getenv("FEISHU_APP_ID") or None,
            app_secret=os.getenv("FEISHU_APP_SECRET") or None,
            app_token=os.getenv("FEISHU_APP_TOKEN") or None,
            table_id=os.getenv("FEISHU_TABLE_ID") or None,
        ),
        target_final_count=450,
        min_valid_result_count=250,
        min_zhilian_result_count=180,
        min_hangzhou_result_count=80,
        company_row_soft_cap=15,
        request_timeout=15,
        max_retries=3,
        target_cities_priority=["杭州", "上海", "南京"],
        keyword_groups={
            "core": ["数据分析", "商业分析", "经营分析", "数据运营", "数据产品分析", "用户研究"],
            "supplemental": ["增长分析", "策略分析", "用户分析", "商业数据分析"],
        },
        zhilian_page_plan=[
            {"city": "杭州", "city_code": "653", "keyword": "数据分析", "max_pages": 4},
            {"city": "杭州", "city_code": "653", "keyword": "数据运营", "max_pages": 3},
            {"city": "杭州", "city_code": "653", "keyword": "商业分析", "max_pages": 2},
            {"city": "杭州", "city_code": "653", "keyword": "经营分析", "max_pages": 2},
            {"city": "杭州", "city_code": "653", "keyword": "数据产品分析", "max_pages": 2},
            {"city": "杭州", "city_code": "653", "keyword": "用户研究", "max_pages": 2},
            {"city": "上海", "city_code": "538", "keyword": "数据分析", "max_pages": 3},
            {"city": "上海", "city_code": "538", "keyword": "数据运营", "max_pages": 2},
            {"city": "上海", "city_code": "538", "keyword": "商业分析", "max_pages": 1},
            {"city": "上海", "city_code": "538", "keyword": "经营分析", "max_pages": 1},
            {"city": "上海", "city_code": "538", "keyword": "数据产品分析", "max_pages": 1},
            {"city": "上海", "city_code": "538", "keyword": "用户研究", "max_pages": 1},
            {"city": "南京", "city_code": "635", "keyword": "数据分析", "max_pages": 2},
            {"city": "南京", "city_code": "635", "keyword": "数据运营", "max_pages": 1},
            {"city": "南京", "city_code": "635", "keyword": "商业分析", "max_pages": 1},
            {"city": "南京", "city_code": "635", "keyword": "经营分析", "max_pages": 1},
            {"city": "南京", "city_code": "635", "keyword": "数据产品分析", "max_pages": 1},
            {"city": "南京", "city_code": "635", "keyword": "用户研究", "max_pages": 1},
        ],
        nowcoder_query_plan=[
            {"city": "杭州", "query": "数据分析 实习 杭州"},
            {"city": "杭州", "query": "商业分析 实习 杭州"},
            {"city": "杭州", "query": "经营分析 实习 杭州"},
            {"city": "杭州", "query": "数据运营 实习 杭州"},
            {"city": "上海", "query": "数据运营 实习 上海"},
            {"city": "上海", "query": "数据分析 实习 上海"},
            {"city": "南京", "query": "数据分析 实习 南京"},
            {"city": "南京", "query": "商业分析 实习 南京"},
        ],
    )


# ==================== 飞书开放平台配置 ====================
runtime_config = get_runtime_config()
FEISHU_APP_ID = runtime_config.feishu.app_id
FEISHU_APP_SECRET = runtime_config.feishu.app_secret
FEISHU_APP_TOKEN = runtime_config.feishu.app_token
FEISHU_TABLE_ID = runtime_config.feishu.table_id

# 飞书 API 基础地址
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# ==================== 兼容旧调用的基础常量 ====================
SEARCH_KEYWORD = "数据分析"
MIN_DELAY = 1
MAX_DELAY = 2
PAGE_TIMEOUT = runtime_config.request_timeout * 1000

PROVINCE_CITIES = {
    "浙江省": ["杭州"],
    "江苏省": ["南京"],
    "上海": ["上海"],
}
TARGET_CITIES = [city for cities in PROVINCE_CITIES.values() for city in cities]
NOWCODER_JOB_TYPES = ["实习"]
ZHILIAN_JOB_TYPES = {"实习": 4}
ZHILIAN_CITY_CODES = {"杭州": "653", "南京": "635", "上海": "538"}
ZHILIAN_MULTI_PAGE_CITIES = {"杭州", "南京", "上海"}
ZHILIAN_MAX_PAGES = 5

TECH_TOOLS = [
    "SQL", "Python", "R语言", "Java", "Scala", "Spark",
    "Hadoop", "Hive", "Flink", "Kafka",
    "Tableau", "Power BI", "PowerBI", "Excel", "SPSS", "SAS",
    "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn",
    "TensorFlow", "PyTorch", "Keras",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "ClickHouse",
    "Airflow", "ETL", "DataX", "Kettle",
    "Git", "Linux", "Shell", "Docker",
    "Looker", "Metabase", "Superset", "FineBI", "FineReport",
    "MATLAB", "Stata",
]

BUSINESS_KEYWORDS = [
    "留存分析", "漏斗模型", "用户画像", "A/B测试", "AB测试",
    "用户增长", "用户生命周期", "LTV", "ROI", "GMV",
    "转化率", "复购率", "DAU", "MAU", "ARPU", "ARPPU",
    "归因分析", "埋点", "数据看板", "数据仓库", "数据中台",
    "指标体系", "数据治理", "数据质量", "需求分析", "竞品分析",
    "市场分析", "行业分析", "商业分析", "财务分析", "风控",
    "推荐系统", "搜索算法", "NLP", "机器学习", "深度学习",
    "数据建模", "数据可视化", "报表", "Dashboard",
]

PLATFORM_URLS = {
    "nowcoder": "https://www.nowcoder.com/search?type=job&searchType=&query={keyword}",
    "zhilian": "https://sou.zhaopin.com/?jl={city}&kw={keyword}&p=1",
}

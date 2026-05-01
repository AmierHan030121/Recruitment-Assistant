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
    notify_receive_id: Optional[str]
    notify_receive_id_type: str


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
    target_cities_priority = ["杭州", "上海", "南京"]
    zhilian_city_codes = {"杭州": "653", "上海": "538", "南京": "635"}
    zhilian_keywords_by_city = {
        # 广度优先：只保留已验证 page1 有真实职位卡片的词，避免浪费在
        # positionCount 看起来很多、但首屏实际为空的查询上。
        "杭州": [
            "数据运营",
            "产品运营",
            "用户运营",
            "运营分析",
            "数据分析",
            "数据治理",
            "行业研究",
            "市场研究",
            "市场分析",
            "商业运营",
            "用户研究",
            "商业分析",
            "商业数据分析",
            "市场运营",
            "内容运营",
            "活动运营",
            "电商运营",
        ],
        "上海": [
            "数据运营",
            "用户运营",
            "运营分析",
            "数据分析",
            "数据治理",
            "市场分析",
            "市场研究",
            "行业研究",
            "产品运营",
            "商业运营",
            "商业分析",
            "用户研究",
            "市场运营",
            "内容运营",
            "活动运营",
            "电商运营",
        ],
        "南京": [
            "数据运营",
            "数据治理",
            "数据分析",
            "市场分析",
            "产品运营",
            "商业分析",
            "市场运营",
            "内容运营",
            "活动运营",
            "电商运营",
        ],
    }
    nowcoder_keywords_by_city = {
        "杭州": ["数据分析", "数据运营", "数据治理", "市场分析", "行业研究", "产品运营"],
        "上海": ["数据分析", "数据运营", "数据治理", "市场分析", "行业研究"],
        "南京": ["数据运营", "数据治理", "数据分析", "市场分析"],
    }

    return RuntimeConfig(
        feishu=FeishuConfig(
            app_id=os.getenv("FEISHU_APP_ID") or None,
            app_secret=os.getenv("FEISHU_APP_SECRET") or None,
            app_token=os.getenv("FEISHU_APP_TOKEN") or None,
            table_id=os.getenv("FEISHU_TABLE_ID") or None,
            notify_receive_id=os.getenv("FEISHU_NOTIFY_RECEIVE_ID") or None,
            notify_receive_id_type=os.getenv("FEISHU_NOTIFY_RECEIVE_ID_TYPE") or "user_id",
        ),
        target_final_count=450,
        min_valid_result_count=250,
        min_zhilian_result_count=180,
        min_hangzhou_result_count=80,
        company_row_soft_cap=15,
        request_timeout=15,
        max_retries=3,
        target_cities_priority=target_cities_priority,
        keyword_groups={
            "core": ["数据运营", "用户运营", "运营分析", "数据分析", "数据治理", "市场分析", "市场研究", "行业研究"],
            "supplemental": [
                "商业分析",
                "商业运营",
                "商业数据分析",
                "产品运营",
                "用户研究",
                "市场运营",
                "内容运营",
                "活动运营",
                "电商运营",
            ],
        },
        zhilian_page_plan=[
            {"city": city, "city_code": zhilian_city_codes[city], "keyword": keyword, "max_pages": 1}
            for city in target_cities_priority
            for keyword in zhilian_keywords_by_city[city]
        ],
        nowcoder_query_plan=[
            {"city": city, "query": f"{keyword} 实习 {city}"}
            for city in target_cities_priority
            for keyword in nowcoder_keywords_by_city[city]
        ],
    )


# ==================== 飞书开放平台配置 ====================
runtime_config = get_runtime_config()
FEISHU_APP_ID = runtime_config.feishu.app_id
FEISHU_APP_SECRET = runtime_config.feishu.app_secret
FEISHU_APP_TOKEN = runtime_config.feishu.app_token
FEISHU_TABLE_ID = runtime_config.feishu.table_id
FEISHU_NOTIFY_RECEIVE_ID = runtime_config.feishu.notify_receive_id
FEISHU_NOTIFY_RECEIVE_ID_TYPE = runtime_config.feishu.notify_receive_id_type

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

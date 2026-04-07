"""
配置模块：管理所有常量、API 密钥和搜索关键词。
优先从环境变量读取敏感信息，适配 GitHub Actions Secrets。
"""

import os

# ==================== 飞书开放平台配置 ====================
# 注意：GitHub Actions 中 Secrets 未配置时环境变量为空字符串，
# 必须用 `or` 而非 getenv 默认值来回退到硬编码值。
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID") or "cli_a958b47358785bd6"
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET") or "S60WUzh6FsMrSF5gyyaPQgkaBNwDNHMQ"
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN") or "GXOvwcD08imZ1lkroOec6P9knlg"
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID") or "tbl2zCRWvAo5WEPN"

# 飞书 API 基础地址
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# ==================== 搜索关键词 ====================
SEARCH_KEYWORD = "数据分析"

# ==================== 爬虫配置 ====================
# 随机延迟范围（秒）
MIN_DELAY = 3
MAX_DELAY = 8

# Playwright 超时时间（毫秒）
PAGE_TIMEOUT = 60000

# ==================== 目标城市列表 ====================
# 省份 → 城市映射（用于牛客网城市级联筛选器导航）
PROVINCE_CITIES = {
    "浙江省": ["杭州"],
    "江苏省": ["南京"],
    "上海": ["上海"],
}

# 扁平化城市列表
TARGET_CITIES = [city for cities in PROVINCE_CITIES.values() for city in cities]

# ==================== 牛客网职位类型 ====================
NOWCODER_JOB_TYPES = ["实习"]

# ==================== 智联招聘职位类型 ====================
# 职位类型 → URL 参数 et 值（直接通过 URL 筛选，无需点击页面筛选器）
ZHILIAN_JOB_TYPES = {"实习": 4}

# ==================== 智联招聘城市编码 ====================
# 智联招聘 URL 中 jl 参数使用数字城市编码（非中文名称）
ZHILIAN_CITY_CODES = {
    "杭州": "653",
    "南京": "635",
    "上海": "538",
}

# ==================== 智联招聘多页抓取 ====================
# 仅 3 个城市 × 1 种类型，全部启用多页（最多 5 页）
ZHILIAN_MULTI_PAGE_CITIES = {"杭州", "南京", "上海"}
ZHILIAN_MAX_PAGES = 5

# ==================== 数据清洗：技术工具关键词 ====================
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

# ==================== 数据清洗：业务关键词 ====================
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

# ==================== 平台 URL 模板 ====================
PLATFORM_URLS = {
    "nowcoder": "https://www.nowcoder.com/search?type=job&searchType=&query={keyword}",
    "zhilian": "https://sou.zhaopin.com/?jl={city}&kw={keyword}&p=1",
}

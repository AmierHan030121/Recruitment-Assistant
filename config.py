"""
配置模块：管理所有常量、API 密钥和搜索关键词。
优先从环境变量读取敏感信息，适配 GitHub Actions Secrets。
"""

import os

# ==================== 飞书开放平台配置 ====================
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")  # 多维表格 app_token
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")    # 多维表格中的数据表 ID

# 飞书 API 基础地址
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# ==================== 搜索关键词 ====================
SEARCH_KEYWORD = "数据分析"

# ==================== 爬虫配置 ====================
# 随机延迟范围（秒）
MIN_DELAY = 3
MAX_DELAY = 8

# 每个平台最大抓取页数
MAX_PAGES = 10

# Playwright 超时时间（毫秒）
PAGE_TIMEOUT = 60000

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
    "shixiseng": "https://www.shixiseng.com/interns?keyword={keyword}&type=intern",
    "zhilian": "https://sou.zhaopin.com/?jl=530&kw={keyword}&p={page}",
}

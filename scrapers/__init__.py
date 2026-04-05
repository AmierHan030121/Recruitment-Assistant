"""
爬虫包初始化：导出各平台爬虫函数。
"""

from scrapers.nowcoder import scrape_nowcoder
from scrapers.zhilian import scrape_zhilian

__all__ = ["scrape_nowcoder", "scrape_zhilian"]

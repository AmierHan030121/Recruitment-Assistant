"""
爬虫包初始化：导出各平台爬虫函数。
"""

__all__ = ["scrape_nowcoder", "scrape_zhilian"]


async def scrape_nowcoder():
    from scrapers.nowcoder import scrape_nowcoder as _scrape_nowcoder

    return await _scrape_nowcoder()


async def scrape_zhilian():
    from scrapers.zhilian import scrape_zhilian as _scrape_zhilian

    return await _scrape_zhilian()

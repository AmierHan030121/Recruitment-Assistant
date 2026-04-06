"""
主入口：协调爬虫、数据清洗、飞书同步的完整执行流程。

执行方式：
    python main.py              # 运行所有平台
    python main.py --platform nowcoder  # 仅运行牛客网
    python main.py --dry-run    # 仅爬取和清洗，不写入飞书
"""

import sys
import os
import asyncio
import logging
import argparse
from datetime import datetime

# 将项目根目录加入 sys.path，确保模块可被正确导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.nowcoder import scrape_nowcoder
from scrapers.zhilian import scrape_zhilian
from cleaner import clean_data
from feishu import sync_to_feishu

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# 平台名称到爬虫函数的映射
SCRAPERS = {
    "nowcoder": ("牛客网", scrape_nowcoder),
    "zhilian": ("智联招聘", scrape_zhilian),
}


async def run_scraper(name: str, scrape_func) -> list:
    """运行单个平台的爬虫，捕获所有异常（含 CancelledError）确保已抓数据能被利用。"""
    try:
        logger.info(f"===== 开始抓取 [{name}] =====")
        results = await scrape_func()
        logger.info(f"[{name}] 抓取完成，获取 {len(results)} 条数据")
        return results
    except BaseException as e:
        # scrape_func 内部已捕获 CancelledError 并返回部分结果，
        # 此处兜底：若仍有异常抛出则记录并返回空列表
        logger.error(f"[{name}] 抓取异常: {e}")
        return []


async def main(platforms: list = None, dry_run: bool = False):
    """
    主流程：
    1. 依次运行各平台爬虫
    2. 合并所有数据并清洗
    3. 同步至飞书多维表格
    """
    start_time = datetime.now()
    logger.info(f"========== 招聘信息自动抓取系统启动 {start_time.strftime('%Y-%m-%d %H:%M:%S')} ==========")

    # 确定要运行的平台
    if platforms:
        target_scrapers = {k: v for k, v in SCRAPERS.items() if k in platforms}
    else:
        target_scrapers = SCRAPERS

    if not target_scrapers:
        logger.error(f"未找到指定平台，可选: {list(SCRAPERS.keys())}")
        return

    # 依次运行各平台爬虫（串行，避免同时开太多浏览器）
    all_jobs = []
    try:
        for key, (name, func) in target_scrapers.items():
            jobs = await run_scraper(name, func)
            all_jobs.extend(jobs)
    except BaseException as e:
        logger.error(f"爬虫主循环中断: {e}（已收集 {len(all_jobs)} 条，继续清洗提交）")
    finally:
        # ⚠️ 无论爬虫是否中途取消，只要有数据就继续清洗和提交
        logger.info(f"所有平台抓取完毕（或中断），原始数据共 {len(all_jobs)} 条")

        if not all_jobs:
            logger.warning("未抓取到任何数据，流程结束")
            return

        # 数据清洗
        logger.info("===== 开始数据清洗 =====")
        df = clean_data(all_jobs)

        if df.empty:
            logger.warning("清洗后数据为空，流程结束")
            return

        # 保存 CSV 到 output 文件夹
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(
            output_dir,
            f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"数据已备份至 {csv_path}")

        # 同步到飞书
        if dry_run:
            logger.info("[DRY RUN] 跳过飞书同步，仅展示数据摘要：")
            logger.info(f"  - 总记录数: {len(df)}")
            logger.info(f"  - 平台分布: {df['来源平台'].value_counts().to_dict()}")
            logger.info(f"  - 岗位类型: {df['岗位类型'].value_counts().to_dict()}")
        else:
            logger.info("===== 开始同步至飞书多维表格 =====")
            new_count = sync_to_feishu(df)
            logger.info(f"飞书同步完成，新增 {new_count} 条记录")

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"========== 流程结束，耗时 {elapsed:.1f} 秒 ==========")


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="招聘信息自动化获取推送助手")
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=list(SCRAPERS.keys()),
        help="指定要抓取的平台（可多选），默认抓取全部",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅抓取和清洗数据，不写入飞书",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(platforms=args.platform, dry_run=args.dry_run))

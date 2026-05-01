"""
主入口：协调智联主抓、牛客补量、数据清洗和飞书同步。
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cleaner import clean_data, validate_final_dataset
from config import get_runtime_config
from feishu import send_completion_notification
from feishu import sync_to_feishu
from scrapers.nowcoder import scrape_nowcoder
from scrapers.zhilian import scrape_zhilian

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

shutdown_requested = False


def _handle_shutdown(signum, frame):
    del frame
    global shutdown_requested
    shutdown_requested = True
    logger.warning(f"收到终止信号 (signal={signum})，将在当前任务完成后退出...")


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


def should_run_nowcoder(current_final_count: int, target_count: int) -> bool:
    return current_final_count < target_count


def save_output_files(raw_jobs: list[dict], final_df: pd.DataFrame, output_dir: Optional[Path] = None) -> dict[str, Path]:
    output_dir = output_dir or Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    label = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = output_dir / f"raw_jobs_{label}.csv"
    final_path = output_dir / f"final_jobs_{label}.csv"

    pd.DataFrame(raw_jobs).to_csv(raw_path, index=False, encoding="utf-8-sig")
    final_df.to_csv(final_path, index=False, encoding="utf-8-sig")
    return {"raw": raw_path, "final": final_path}


async def run_scraper(name: str, scrape_func) -> list:
    try:
        logger.info(f"===== 开始抓取 [{name}] =====")
        results = await scrape_func()
        logger.info(f"[{name}] 抓取完成，获取 {len(results)} 条数据")
        return results
    except BaseException as exc:
        logger.error(f"[{name}] 抓取异常: {exc}")
        return []


async def main(platforms: list = None, dry_run: bool = False):
    cfg = get_runtime_config()
    start_time = datetime.now()
    logger.info(f"========== 招聘信息自动抓取系统启动 {start_time.strftime('%Y-%m-%d %H:%M:%S')} ==========")

    platforms = platforms or ["zhilian", "nowcoder"]
    requested = set(platforms)
    all_jobs = []
    source_counts = {"智联招聘": 0, "牛客网": 0}

    if "zhilian" in requested and not shutdown_requested:
        zhilian_jobs = await run_scraper("智联招聘", scrape_zhilian)
        source_counts["智联招聘"] = len(zhilian_jobs)
        all_jobs.extend(zhilian_jobs)

    interim_df = clean_data(all_jobs, target_count=cfg.target_final_count)

    if (
        "nowcoder" in requested
        and not shutdown_requested
        and should_run_nowcoder(len(interim_df), cfg.target_final_count)
    ):
        nowcoder_jobs = await run_scraper("牛客网", scrape_nowcoder)
        source_counts["牛客网"] = len(nowcoder_jobs)
        all_jobs.extend(nowcoder_jobs)

    final_df = clean_data(all_jobs, target_count=cfg.target_final_count)
    output_paths = save_output_files(all_jobs, final_df)
    logger.info(f"原始数据已保存到 {output_paths['raw']}")
    logger.info(f"最终数据已保存到 {output_paths['final']}")

    quality_ok, reasons = validate_final_dataset(final_df, source_counts)

    if dry_run:
        logger.info("[DRY RUN] 跳过飞书同步")
    else:
        if not quality_ok:
            for reason in reasons:
                logger.error(reason)
            raise SystemExit(1)
        logger.info("===== 开始同步至飞书多维表格 =====")
        written = sync_to_feishu(final_df)
        logger.info(f"飞书同步完成，写入 {written} 条记录")
        send_completion_notification(
            written=written,
            elapsed_seconds=(datetime.now() - start_time).total_seconds(),
        )

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"========== 流程结束，耗时 {elapsed:.1f} 秒 ==========")


def parse_args():
    parser = argparse.ArgumentParser(description="招聘信息自动化获取推送助手")
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=["nowcoder", "zhilian"],
        help="指定要抓取的平台（可多选），默认抓取全部",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅抓取和清洗，不写入飞书",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(platforms=args.platform, dry_run=args.dry_run))

"""
飞书多维表格 (Bitable) 集成模块：
1. 获取 tenant_access_token（自动认证）
2. 查询已有记录，实现"公司名+岗位名"去重
3. 批量写入新岗位数据到多维表格
"""

import logging
import requests
import pandas as pd
from typing import Set
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID,
    FEISHU_BASE_URL,
)

logger = logging.getLogger(__name__)


class FeishuBitable:
    """飞书多维表格操作封装。"""

    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.app_token = FEISHU_APP_TOKEN
        self.table_id = FEISHU_TABLE_ID
        self.base_url = FEISHU_BASE_URL
        self.tenant_token = ""

    def authenticate(self) -> bool:
        """
        获取飞书 tenant_access_token。
        文档: https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal
        """
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                self.tenant_token = data["tenant_access_token"]
                logger.info("飞书认证成功，已获取 tenant_access_token")
                return True
            else:
                logger.error(f"飞书认证失败: {data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"飞书认证请求异常: {e}")
            return False

    def _headers(self) -> dict:
        """构造带认证的请求头。"""
        return {
            "Authorization": f"Bearer {self.tenant_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def get_existing_keys(self) -> Set[str]:
        """
        查询多维表格中已有的所有记录，提取"公司名称_岗位名称"作为唯一键。
        用于后续去重判断，避免重复写入。

        使用分页方式获取所有记录。
        文档: https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/list
        """
        existing_keys: Set[str] = set()
        page_token = ""
        has_more = True

        while has_more:
            url = (
                f"{self.base_url}/bitable/v1/apps/{self.app_token}"
                f"/tables/{self.table_id}/records"
            )
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            try:
                resp = requests.get(url, headers=self._headers(), params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    logger.error(f"获取已有记录失败: {data.get('msg')}")
                    break

                items = data.get("data", {}).get("items", [])
                for item in items:
                    fields = item.get("fields", {})
                    company = fields.get("公司名称", "")
                    job_name = fields.get("岗位名称", "")
                    if company and job_name:
                        # 处理飞书返回的可能是列表类型的字段
                        if isinstance(company, list):
                            company = company[0].get("text", "") if company else ""
                        if isinstance(job_name, list):
                            job_name = job_name[0].get("text", "") if job_name else ""
                        key = f"{str(company).strip()}_{str(job_name).strip()}"
                        existing_keys.add(key)

                has_more = data.get("data", {}).get("has_more", False)
                page_token = data.get("data", {}).get("page_token", "")

            except Exception as e:
                logger.error(f"查询已有记录异常: {e}")
                break

        logger.info(f"飞书表格中已有 {len(existing_keys)} 条记录")
        return existing_keys

    def batch_create_records(self, df: pd.DataFrame, existing_keys: Set[str]) -> int:
        """
        将 DataFrame 中的新增岗位数据批量写入飞书多维表格。
        跳过 existing_keys 中已存在的记录。

        飞书批量创建 API 每次最多 500 条。
        文档: https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/batch_create
        """
        url = (
            f"{self.base_url}/bitable/v1/apps/{self.app_token}"
            f"/tables/{self.table_id}/records/batch_create"
        )

        new_records = []
        for _, row in df.iterrows():
            unique_key = row.get("unique_key", "")
            if unique_key in existing_keys:
                continue

            record = {
                "fields": {
                    "公司名称": str(row.get("公司名称", "")),
                    "岗位名称": str(row.get("岗位名称", "")),
                    "薪资原始": str(row.get("薪资原始", "")),
                    "薪资下限": str(row.get("薪资下限", "")),
                    "薪资上限": str(row.get("薪资上限", "")),
                    "工作地点": str(row.get("工作地点", "")),
                    "岗位描述": str(row.get("岗位描述", "")),
                    "岗位类型": str(row.get("岗位类型", "")),
                    "来源平台": str(row.get("来源平台", "")),
                    "技术工具": str(row.get("技术工具", "")),
                    "业务关键词": str(row.get("业务关键词", "")),
                }
            }
            new_records.append(record)

        if not new_records:
            logger.info("没有新增岗位数据需要写入")
            return 0

        # 分批写入（每批最多 500 条）
        total_created = 0
        batch_size = 500
        for i in range(0, len(new_records), batch_size):
            batch = new_records[i: i + batch_size]
            payload = {"records": batch}

            try:
                resp = requests.post(
                    url, headers=self._headers(), json=payload, timeout=30
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") == 0:
                    created = len(data.get("data", {}).get("records", []))
                    total_created += created
                    logger.info(
                        f"第 {i // batch_size + 1} 批写入成功: {created} 条"
                    )
                else:
                    logger.error(f"批量写入失败: {data.get('msg')}")
            except Exception as e:
                logger.error(f"批量写入请求异常: {e}")

        logger.info(f"总共新增写入 {total_created} 条岗位数据")
        return total_created


def sync_to_feishu(df: pd.DataFrame) -> int:
    """
    顶层便捷函数：认证 → 查已有数据 → 去重写入。
    返回实际新增的记录数。
    """
    if df.empty:
        logger.warning("DataFrame 为空，跳过飞书同步")
        return 0

    bitable = FeishuBitable()

    # 检查必要配置
    if not all([bitable.app_id, bitable.app_secret, bitable.app_token, bitable.table_id]):
        logger.error(
            "飞书配置不完整，请设置环境变量: "
            "FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN, FEISHU_TABLE_ID"
        )
        return 0

    # 1. 认证
    if not bitable.authenticate():
        return 0

    # 2. 获取已有记录的唯一键
    existing_keys = bitable.get_existing_keys()

    # 3. 批量写入新数据
    return bitable.batch_create_records(df, existing_keys)

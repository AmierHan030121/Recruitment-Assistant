from pathlib import Path

import pandas as pd
import pytest

from feishu import FeishuBitable
from feishu import sync_to_feishu


def test_feishu_config_requires_environment_values(monkeypatch):
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN", "FEISHU_TABLE_ID"):
        monkeypatch.delenv(key, raising=False)
    bitable = FeishuBitable()
    assert bitable.app_id is None
    assert bitable.app_secret is None
    assert bitable.app_token is None
    assert bitable.table_id is None


def test_sync_to_feishu_raises_when_required_env_missing(monkeypatch):
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN", "FEISHU_TABLE_ID"):
        monkeypatch.delenv(key, raising=False)

    df = pd.DataFrame(
        [
            {
                "公司名称": "测试公司",
                "岗位名称": "数据分析实习生",
                "薪资": "150-200元/天",
                "工作地点": "杭州",
                "岗位描述": "SQL Python",
                "岗位类型": "实习",
                "来源平台": "智联招聘",
                "技术工具": "SQL, Python",
                "业务关键词": "数据分析",
            }
        ]
    )

    with pytest.raises(RuntimeError, match="飞书配置不完整"):
        sync_to_feishu(df)


def test_ci_files_install_playwright_runtime_for_zhilian_fallback():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/main.yml").read_text(encoding="utf-8")
    assert "playwright>=" in requirements.lower()
    assert "python -m playwright install --with-deps chromium" in workflow.lower()
    assert "ms-playwright" in workflow.lower()

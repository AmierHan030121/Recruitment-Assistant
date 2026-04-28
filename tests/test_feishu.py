from pathlib import Path

from feishu import FeishuBitable


def test_feishu_config_requires_environment_values(monkeypatch):
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN", "FEISHU_TABLE_ID"):
        monkeypatch.delenv(key, raising=False)
    bitable = FeishuBitable()
    assert bitable.app_id is None
    assert bitable.app_secret is None
    assert bitable.app_token is None
    assert bitable.table_id is None


def test_ci_files_no_longer_reference_playwright_runtime():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/main.yml").read_text(encoding="utf-8")
    assert "playwright" not in requirements.lower()
    assert "install playwright" not in workflow.lower()
    assert "ms-playwright" not in workflow.lower()

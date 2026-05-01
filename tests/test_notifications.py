import json
import asyncio
from pathlib import Path

import pandas as pd

import feishu
import main


def test_send_completion_notification_posts_app_message(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_test")
    monkeypatch.setenv("FEISHU_NOTIFY_RECEIVE_ID", "7369989526749544449")
    assert hasattr(feishu, "send_completion_notification")

    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0}

    def fake_authenticate(self):
        self.tenant_token = "tenant-token"
        return True

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(feishu.FeishuBitable, "authenticate", fake_authenticate)
    monkeypatch.setattr(feishu.requests, "post", fake_post)

    ok = feishu.send_completion_notification(written=293, elapsed_seconds=137.0)

    assert ok is True
    assert captured["url"] == "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=user_id"
    assert captured["headers"]["Authorization"] == "Bearer tenant-token"
    assert captured["json"]["receive_id"] == "7369989526749544449"
    assert captured["json"]["msg_type"] == "text"
    assert "293" in json.loads(captured["json"]["content"])["text"]
    assert "137.0" in json.loads(captured["json"]["content"])["text"]


def test_main_sends_completion_notification_after_feishu_sync(monkeypatch, tmp_path):
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

    raw_path = tmp_path / "raw.csv"
    final_path = tmp_path / "final.csv"
    raw_path.write_text("", encoding="utf-8")
    final_path.write_text("", encoding="utf-8")

    events = []

    monkeypatch.setattr(main, "clean_data", lambda jobs, target_count: df)
    monkeypatch.setattr(main, "validate_final_dataset", lambda final_df, source_counts: (True, []))
    monkeypatch.setattr(
        main,
        "save_output_files",
        lambda raw_jobs, final_df, output_dir=None: {"raw": raw_path, "final": final_path},
    )

    def fake_sync(final_df):
        events.append(("sync", len(final_df)))
        return 42

    def fake_notify(written, elapsed_seconds):
        events.append(("notify", written, elapsed_seconds))
        return True

    def fake_save_run_summary(summary, output_dir=None):
        events.append(("summary", summary, output_dir))
        return tmp_path / "run_summary.json"

    monkeypatch.setattr(main, "sync_to_feishu", fake_sync)
    monkeypatch.setattr(main, "send_completion_notification", fake_notify, raising=False)
    monkeypatch.setattr(main, "save_run_summary", fake_save_run_summary, raising=False)

    asyncio.run(main.main(platforms=["placeholder"], dry_run=False))

    assert events[0] == ("sync", 1)
    assert events[1][0] == "notify"
    assert events[1][1] == 42
    assert events[1][2] >= 0
    assert events[2][0] == "summary"
    assert events[2][1]["written_count"] == 42
    assert events[2][1]["notification_sent"] is True

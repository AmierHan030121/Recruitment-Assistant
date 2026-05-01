from config import get_runtime_config
from scrapers.base import build_default_headers, build_session


def test_runtime_config_does_not_fall_back_to_hardcoded_feishu(monkeypatch):
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN", "FEISHU_TABLE_ID"):
        monkeypatch.delenv(key, raising=False)
    cfg = get_runtime_config()
    assert cfg.feishu.app_id is None
    assert cfg.feishu.app_secret is None
    assert cfg.feishu.app_token is None
    assert cfg.feishu.table_id is None


def test_runtime_config_contains_hangzhou_first_single_page_plan():
    cfg = get_runtime_config()
    first = cfg.zhilian_page_plan[0]
    assert first["city"] == "杭州"
    assert first["keyword"] == "数据运营"
    assert first["max_pages"] == 1
    assert all(item["max_pages"] == 1 for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "杭州" and item["keyword"] == "数据治理" for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "杭州" and item["keyword"] == "运营分析" for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "杭州" and item["keyword"] == "市场运营" for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "杭州" and item["keyword"] == "内容运营" for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "上海" and item["keyword"] == "活动运营" for item in cfg.zhilian_page_plan)
    assert any(item["city"] == "南京" and item["keyword"] == "电商运营" for item in cfg.zhilian_page_plan)


def test_http_session_has_browser_like_headers():
    headers = build_default_headers()
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert headers["Accept-Language"] == "zh-CN,zh;q=0.9"
    session = build_session()
    assert session.headers["Accept-Language"] == "zh-CN,zh;q=0.9"

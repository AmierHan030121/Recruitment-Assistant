from cleaner import clean_data, validate_final_dataset


RAW_JOBS = [
    {
        "岗位名称": "数据分析实习生",
        "公司名称": "甲公司",
        "薪资": "200-300元/天",
        "工作地点": "杭州·西湖",
        "岗位描述": "SQL Python 数据看板",
        "岗位类型": "实习",
        "来源平台": "智联招聘",
        "原始ID": "z1",
        "抓取关键词": "数据分析",
        "抓取城市": "杭州",
        "发布时间": "2025-11-01 10:00:00",
    },
    {
        "岗位名称": "数据分析实习生",
        "公司名称": "甲公司",
        "薪资": "200-300元/天",
        "工作地点": "杭州市",
        "岗位描述": "SQL Python 数据看板",
        "岗位类型": "实习",
        "来源平台": "牛客网",
        "原始ID": "n1",
        "抓取关键词": "数据分析 实习 杭州",
        "抓取城市": "杭州",
        "发布时间": "2025-11-01 10:00:00",
    },
]


def test_clean_data_deduplicates_across_platforms():
    df = clean_data(RAW_JOBS, target_count=450)
    assert len(df) == 1
    assert df.iloc[0]["工作地点"] == "杭州"


def test_clean_data_caps_result_length():
    df = clean_data(RAW_JOBS * 500, target_count=450)
    assert len(df) <= 450


def test_validate_final_dataset_checks_minimums():
    df = clean_data(RAW_JOBS, target_count=450)
    ok, reasons = validate_final_dataset(
        df,
        source_counts={"智联招聘": 1, "牛客网": 0},
    )
    assert ok is False
    assert any("最低有效数" in reason for reason in reasons)

from tests.helpers import read_fixture
from scrapers.zhilian import (
    extract_initial_state,
    parse_zhilian_positions,
    parse_zhilian_job_cards,
)


def test_extract_initial_state_reads_embedded_json():
    state = extract_initial_state(read_fixture("zhilian", "search_page.html"))
    assert state["positionCount"] == 59
    assert state["pages"] == 3


def test_parse_zhilian_positions_uses_embedded_description():
    state = extract_initial_state(read_fixture("zhilian", "search_page.html"))
    jobs = parse_zhilian_positions(state, city_name="上海", keyword="数据分析")
    assert len(jobs) == 1
    assert jobs[0]["岗位名称"] == "数据调查分析（实习）"
    assert jobs[0]["公司名称"] == "上海数治数据科技有限公司"
    assert jobs[0]["岗位描述"].startswith("招聘岗位：数据调查分析")
    assert jobs[0]["原始ID"] == "CC841423530J40895236315"


def test_extract_initial_state_surfaces_page_context_when_state_missing():
    html = read_fixture("zhilian", "failure_page.html")
    try:
        extract_initial_state(html)
    except ValueError as exc:
        message = str(exc)
        assert "未找到智联 __INITIAL_STATE__" in message
        assert "杭州数据分析招聘信息" in message
        assert "未包含嵌入式职位状态数据" in message
    else:
        raise AssertionError("expected extract_initial_state to raise ValueError")


def test_parse_zhilian_job_cards_extracts_basic_fields_without_state():
    jobs = parse_zhilian_job_cards(
        read_fixture("zhilian", "search_page_cards.html"),
        city_name="杭州",
        keyword="数据分析",
    )
    assert len(jobs) == 2
    assert jobs[0]["岗位名称"] == "数据分析师（实习）"
    assert jobs[0]["公司名称"] == "浙江汇信科技有限公司"
    assert jobs[0]["薪资"] == "150-200元/天"
    assert jobs[0]["工作地点"] == "杭州·拱墅·米市巷"
    assert jobs[0]["原始ID"] == "CC146609540J40844908101"
    assert jobs[0]["来源平台"] == "智联招聘"

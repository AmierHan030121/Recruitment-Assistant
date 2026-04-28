from tests.helpers import read_fixture
from scrapers.zhilian import extract_initial_state, parse_zhilian_positions


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

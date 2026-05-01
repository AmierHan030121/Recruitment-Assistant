from tests.helpers import read_fixture
from scrapers.nowcoder import parse_nowcoder_search_results, parse_nowcoder_job_detail


def test_parse_nowcoder_search_results_filters_city_and_role_family():
    jobs = parse_nowcoder_search_results(
        read_fixture("nowcoder", "search_page.html"),
        target_city="杭州",
        keyword="数据分析",
    )
    assert len(jobs) == 1
    assert jobs[0]["岗位名称"] == "[2027届实习可留用-杭州]数据分析实习生"
    assert jobs[0]["工作地点"] == "杭州"


def test_parse_nowcoder_job_detail_extracts_description():
    detail = parse_nowcoder_job_detail(read_fixture("nowcoder", "detail_page.html"))
    assert detail["岗位名称"] == "数据分析师（实习）"
    assert detail["公司名称"] == "行吟信息科技（上海）有限公司"
    assert "岗位职责" in detail["岗位描述"]
    assert "SQL" in detail["岗位描述"]


def test_parse_nowcoder_search_results_accepts_expanded_role_family_terms():
    html = """
    <html><body>
      <a href="/jobs/detail/900001">
        数据治理实习生
        180-220元/天
        杭州
      </a>
    </body></html>
    """

    jobs = parse_nowcoder_search_results(html, target_city="杭州", keyword="数据治理")

    assert len(jobs) == 1
    assert jobs[0]["岗位名称"] == "数据治理实习生"

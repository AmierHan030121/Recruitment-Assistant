from tests.helpers import read_fixture
from scrapers.nowcoder import build_nowcoder_queries, collect_nowcoder_jobs


def test_build_nowcoder_queries_starts_with_hangzhou_queries():
    queries = build_nowcoder_queries()
    assert queries[0]["city"] == "杭州"
    assert "杭州" in queries[0]["query"]


def test_collect_nowcoder_jobs_fetches_detail_for_matching_cards_only():
    search_html = read_fixture("nowcoder", "search_page.html")
    detail_html = read_fixture("nowcoder", "detail_page.html")
    requested_urls = []

    def fake_fetch(_session, url, **_kwargs):
        requested_urls.append(url)
        if "search/job" in url:
            return search_html
        return detail_html

    jobs = collect_nowcoder_jobs(fetch_html=fake_fetch, needed_count=1)
    assert len(jobs) == 1
    assert jobs[0]["岗位名称"] == "数据分析师（实习）"
    assert any("/jobs/detail/" in url for url in requested_urls)

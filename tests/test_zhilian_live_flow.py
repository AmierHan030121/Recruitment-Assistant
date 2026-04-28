from tests.helpers import read_fixture
from scrapers.zhilian import build_zhilian_page_queue, collect_zhilian_jobs


def test_build_zhilian_page_queue_prioritizes_hangzhou_first():
    queue = build_zhilian_page_queue()
    assert queue[0]["city"] == "杭州"
    assert queue[0]["keyword"] == "数据分析"
    assert queue[1]["city"] == "杭州"


def test_collect_zhilian_jobs_deduplicates_on_original_id():
    html = read_fixture("zhilian", "search_page.html")
    calls = []

    def fake_fetch(_session, url, **_kwargs):
        calls.append(url)
        return html

    jobs = collect_zhilian_jobs(fetch_html=fake_fetch, target_pool=1)
    assert len(jobs) == 1
    assert jobs[0]["原始ID"] == "CC841423530J40895236315"
    assert calls

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


def test_collect_zhilian_jobs_falls_back_to_html_cards_when_state_missing():
    html = read_fixture("zhilian", "search_page_cards.html")

    def fake_fetch(_session, _url, **_kwargs):
        return html

    jobs = collect_zhilian_jobs(fetch_html=fake_fetch, target_pool=2)
    assert len(jobs) == 2
    assert jobs[0]["公司名称"] == "浙江汇信科技有限公司"
    assert jobs[1]["原始ID"] == "CC121031870J40793527507"


def test_collect_zhilian_jobs_uses_browser_fallback_on_security_verification_page():
    blocked_html = read_fixture("zhilian", "security_verification_page.html")
    browser_html = read_fixture("zhilian", "search_page.html")
    browser_calls = []

    def fake_fetch(_session, _url, **_kwargs):
        return blocked_html

    def fake_browser_fetch(_session, url, **_kwargs):
        browser_calls.append(url)
        return browser_html

    jobs = collect_zhilian_jobs(
        fetch_html=fake_fetch,
        fetch_browser_html=fake_browser_fetch,
        target_pool=1,
    )

    assert len(jobs) == 1
    assert jobs[0]["原始ID"] == "CC841423530J40895236315"
    assert browser_calls


def test_collect_zhilian_jobs_keeps_configured_pages_when_browser_state_reports_one_page():
    import scrapers.zhilian as zhilian

    blocked_html = read_fixture("zhilian", "security_verification_page.html")
    browser_calls = []
    original_queue = zhilian.build_zhilian_page_queue

    def fake_fetch(_session, _url, **_kwargs):
        return blocked_html

    def fake_browser_fetch(_session, url, **_kwargs):
        browser_calls.append(url)
        page_no = len(browser_calls)
        return f"""
        <html><body><script>
        __INITIAL_STATE__={{
            "pages":1,
            "positionList":[{{
                "name":"数据分析实习生{page_no}",
                "companyName":"公司{page_no}",
                "salary60":"150-200元/天",
                "workCity":"杭州",
                "number":"TEST{page_no}",
                "positionURL":"http://www.zhaopin.com/jobdetail/TEST{page_no}.htm",
                "publishTime":"2026-05-01 09:00:00",
                "jobDetailData":{{"position":{{"desc":{{"description":"desc{page_no}"}}}}}}
            }}]
        }}
        </script></body></html>
        """

    zhilian.build_zhilian_page_queue = lambda: [
        {"city": "杭州", "city_code": "653", "keyword": "数据分析", "max_pages": 2}
    ]
    try:
        jobs = collect_zhilian_jobs(
            fetch_html=fake_fetch,
            fetch_browser_html=fake_browser_fetch,
            target_pool=2,
        )
    finally:
        zhilian.build_zhilian_page_queue = original_queue

    assert len(jobs) == 2
    assert [job["原始ID"] for job in jobs] == ["TEST1", "TEST2"]
    assert browser_calls == [
        "https://www.zhaopin.com/sou/?jl=653&kw=%E6%95%B0%E6%8D%AE%E5%88%86%E6%9E%90&p=1&et=4",
        "https://www.zhaopin.com/sou/?jl=653&kw=%E6%95%B0%E6%8D%AE%E5%88%86%E6%9E%90&p=2&et=4",
    ]

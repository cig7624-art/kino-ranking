from playwright.sync_api import sync_playwright
import json

SEARCH_WORD = "멋진 신세계"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )

    context = browser.new_context(
        viewport={"width": 430, "height": 1600},
        locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

    page = context.new_page()
    calls = []

    def handle_response(response):
        if "graphql" in response.url:
            try:
                req = response.request
                calls.append({
                    "url": response.url,
                    "method": req.method,
                    "post_data": req.post_data
                })
            except Exception as e:
                calls.append({"error": str(e)})

    page.on("response", handle_response)

    page.goto(
        f"https://m.kinolights.com/search?keyword={SEARCH_WORD}",
        wait_until="networkidle",
        timeout=60000
    )
    page.wait_for_timeout(5000)

    # 검색 결과 첫 번째 상세 링크 클릭 시도
    try:
        first_link = page.locator("a[href*='/title/'], a[href*='/season/'], a[href*='/movie/'], a[href*='/content/']").first
        href = first_link.get_attribute("href")

        if href:
            if href.startswith("/"):
                href = "https://m.kinolights.com" + href

            page.goto(href, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(7000)
    except Exception as e:
        calls.append({"click_error": str(e)})

    context.close()
    browser.close()

    with open("detail_graphql_calls.json", "w", encoding="utf-8") as f:
        json.dump(calls, f, ensure_ascii=False, indent=2)

    print("DONE")

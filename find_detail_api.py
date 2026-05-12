from playwright.sync_api import sync_playwright
import json

URL = "https://m.kinolights.com/search"
SEARCH_WORD = "멋진 신세계"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 430, "height": 1600},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

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
            except:
                pass

    page.on("response", handle_response)

    page.goto("https://m.kinolights.com", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    # 검색 아이콘 클릭
    page.get_by_placeholder("작품명, 배우, 감독 검색").click(timeout=5000)
    page.keyboard.type(SEARCH_WORD)
    page.wait_for_timeout(3000)

    # 검색 결과 첫 번째 작품 클릭
    page.get_by_text("멋진 신세계").first.click(force=True)
    page.wait_for_timeout(5000)

    browser.close()

    with open("detail_graphql_calls.json", "w", encoding="utf-8") as f:
        json.dump(calls, f, ensure_ascii=False, indent=2)

    print("DONE")

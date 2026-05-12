from playwright.sync_api import sync_playwright
import json

URL = "https://m.kinolights.com/ranking/kino"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 430, "height": 1600},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148"
        )
    )

    graphql_calls = []

    def handle_response(response):
        url = response.url

        if "graphql" in url:
            try:
                req = response.request

                item = {
                    "url": url,
                    "method": req.method,
                    "post_data": req.post_data
                }

                graphql_calls.append(item)

            except Exception:
                pass

    page.on("response", handle_response)

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    buttons = [
        "일간", "주간", "월간",
        "전체", "넷플릭스", "티빙",
        "쿠팡플레이", "웨이브",
        "디즈니+", "왓챠", "박스오피스"
    ]

    for text in buttons:
        try:
            loc = page.get_by_text(text, exact=True)

            for i in range(loc.count()):
                item = loc.nth(i)

                if item.is_visible():
                    item.click(force=True)
                    page.wait_for_timeout(2500)
                    break

        except Exception:
            pass

    browser.close()

    with open("graphql_calls.json", "w", encoding="utf-8") as f:
        json.dump(graphql_calls, f, ensure_ascii=False, indent=2)

    print("DONE")

from playwright.sync_api import sync_playwright
import json

URL = "https://m.kinolights.com/ranking/kino"

KEYWORDS = [
    "ranking",
    "rank",
    "kino",
    "contents",
    "content",
    "ott",
    "search",
    "discover",
    "explore"
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 430, "height": 1600},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148"
        )
    )

    found = []

    def handle_response(response):
        url = response.url
        lower_url = url.lower()

        if any(k in lower_url for k in KEYWORDS):
            try:
                content_type = response.headers.get("content-type", "")
                status = response.status

                item = {
                    "status": status,
                    "content_type": content_type,
                    "url": url
                }

                found.append(item)

            except Exception:
                pass

    page.on("response", handle_response)

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    # 기간/OTT 버튼을 실제로 눌러보면서 네트워크 요청 잡기
    buttons = [
        "일간", "주간", "월간",
        "전체", "넷플릭스", "티빙", "쿠팡플레이",
        "웨이브", "디즈니+", "왓챠", "박스오피스"
    ]

    for text in buttons:
        try:
            loc = page.get_by_text(text, exact=True)
            count = loc.count()

            for i in range(count):
                item = loc.nth(i)

                if item.is_visible():
                    item.click(force=True)
                    page.wait_for_timeout(2500)
                    break

        except Exception as e:
            print(f"CLICK FAIL: {text} / {e}")

    browser.close()

    # 중복 제거
    unique = []
    seen = set()

    for item in found:
        url = item["url"]

        if url not in seen:
            seen.add(url)
            unique.append(item)

    print("\n=== POSSIBLE API URLS ===\n")

    for item in unique:
        print(f"[{item['status']}] {item['content_type']}")
        print(item["url"])
        print("-" * 80)

    with open("api_candidates.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

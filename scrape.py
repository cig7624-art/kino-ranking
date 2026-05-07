from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

URL = "https://m.kinolights.com/ranking/kino"

PERIODS = ["일간", "주간", "월간"]
PLATFORMS = ["전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠", "박스오피스"]

EXCLUDE = set(PERIODS + PLATFORMS + [
    "트렌드 랭킹",
    "성별 · 연령 전체",
    "성별과 연령을 선택하고",
    "꼭 맞는 랭킹을 확인해 보세요",
    "홈", "랭킹", "탐색", "혜택", "마이페이지",
    "집계 기준"
])

def is_title(line):
    if not line or line in EXCLUDE:
        return False
    if re.fullmatch(r"\d{1,3}", line):
        return False
    if re.fullmatch(r"\d+[▲▼]?", line):
        return False
    if re.fullmatch(r"\d+(\.\d+)?%", line):
        return False
    if re.search(r"(드라마|영화|예능|애니메이션|다큐멘터리|시사교양)\s*·\s*\d{4}", line):
        return False
    if "기준" in line:
        return False
    if "업데이트" in line:
        return False
    return True

def extract_titles(page):
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(600)

    for _ in range(10):
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(400)

    text = page.locator("body").inner_text()
    lines = [x.strip() for x in text.split("\n") if x.strip()]

    titles = []

    for line in lines:
        if is_title(line) and line not in titles:
            titles.append(line)

    return titles[:100]

def click_visible_text(page, text):
    loc = page.get_by_text(text, exact=True)
    count = loc.count()

    for i in range(count):
        item = loc.nth(i)

        try:
            if item.is_visible():
                item.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                item.click(force=True)
                page.wait_for_timeout(2000)
                return True
        except Exception:
            pass

    return False

def collect_current(page, period, platform):
    titles = extract_titles(page)

    rows = []
    for idx, title in enumerate(titles, start=1):
        rows.append({
            "date": today,
            "period": period,
            "platform": platform,
            "rank": idx,
            "title": title
        })

    print(f"{period} / {platform} / {len(titles)}개 수집 / 1위: {titles[0] if titles else '-'}")
    return rows

today = datetime.today().strftime("%Y-%m-%d")
rows = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 430, "height": 1600},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
    )

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    for period in PERIODS:
        clicked_period = click_visible_text(page, period)
        print(f"기간 클릭: {period} / {clicked_period}")

        for platform in PLATFORMS:
            clicked_platform = click_visible_text(page, platform)
            print(f"OTT 클릭: {platform} / {clicked_platform}")

            titles = extract_titles(page)

            if len(titles) == 0:
                print(f"스킵: {period} / {platform} / 데이터 없음")
                continue

            for idx, title in enumerate(titles, start=1):
                rows.append({
                    "date": today,
                    "period": period,
                    "platform": platform,
                    "rank": idx,
                    "title": title
                })

            print(f"저장: {period} / {platform} / {len(titles)}개 / 1위: {titles[0]}")

    browser.close()

new_df = pd.DataFrame(rows)

if new_df.empty:
    raise Exception("수집된 데이터가 없습니다. 키노라이츠 페이지 구조가 바뀌었거나 클릭이 실패했습니다.")

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)

    for col in ["period", "platform"]:
        if col not in old.columns:
            old[col] = "전체"

    df = pd.concat([old, new_df], ignore_index=True)

    df = df.drop_duplicates(
        subset=["date", "period", "platform", "rank"],
        keep="last"
    )
else:
    df = new_df

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print("완료")
print(new_df.groupby(["period", "platform"])["title"].first())

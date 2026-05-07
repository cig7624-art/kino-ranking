from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

URL = "https://m.kinolights.com/ranking/kino"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={"width": 390, "height": 1200},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )

    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)

    text = page.locator("body").inner_text()
    browser.close()

lines = [x.strip() for x in text.split("\n") if x.strip()]

titles = []

for i, line in enumerate(lines):
    # 순위 숫자 다음에 나오는 작품명을 잡는 방식
    if re.fullmatch(r"\d{1,3}", line):
        if i + 1 < len(lines):
            title = lines[i + 1]
            if title not in ["일간", "주간", "월간", "전체"] and title not in titles:
                titles.append(title)

titles = titles[:20]

today = datetime.today().strftime("%Y-%m-%d")

df = pd.DataFrame({
    "date": [today] * len(titles),
    "rank": range(1, len(titles) + 1),
    "title": titles
})

csv_path = Path("ranking_history.csv")

if csv_path.exists():
    old = pd.read_csv(csv_path)
    df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(subset=["date", "title"])

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(df.tail(20))

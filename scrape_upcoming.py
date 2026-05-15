import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


OUTPUT = Path("upcoming_releases.csv")
DEBUG_TEXT = Path("debug_upcoming_text.txt")

URLS = [
    "https://kinolights.com/new?tab=upcoming",
    "https://m.kinolights.com/new?tab=upcoming",
]


def save_empty():
    df = pd.DataFrame(
        columns=["collect_date", "release_date", "title", "provider", "genre"]
    )
    df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")


def scrape_debug():
    today = datetime.now().strftime("%Y-%m-%d")

    all_texts = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 2200},
            user_agent="Mozilla/5.0"
        )

        for url in URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(6000)

                # 스크롤해서 lazy load 유도
                for _ in range(5):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(800)

                body_text = page.locator("body").inner_text(timeout=15000)

                all_texts.append(f"\n\n===== URL: {url} =====\n")
                all_texts.append(body_text)

                print(f"{url} text length:", len(body_text))

            except Exception as e:
                all_texts.append(f"\n\n===== URL: {url} FAILED =====\n{e}\n")
                print(f"{url} 실패:", e)

        browser.close()

    DEBUG_TEXT.write_text("\n".join(all_texts), encoding="utf-8")

    # 일단 비어 있는 CSV라도 생성
    save_empty()

    print(f"{DEBUG_TEXT} 저장 완료")
    print(f"{OUTPUT} 빈 파일 저장 완료")
    print(f"collect_date: {today}")


if __name__ == "__main__":
    scrape_debug()

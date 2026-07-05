# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_URL = "https://m.kinolights.com"
TARGET_URL = "https://m.kinolights.com/new?tab=upcoming"

OUT_CSV = Path("upcoming_releases.csv")
DEBUG_TEXT = Path("debug_upcoming_text.txt")
DEBUG_CARDS = Path("debug_upcoming_cards.csv")
DEBUG_SCREENSHOT = Path("debug_upcoming.png")

COLUMNS = ["collect_date", "release_date", "title", "provider", "genre", "url", "image_url"]

PROVIDERS = [
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "디즈니+",
    "웨이브",
    "라프텔",
    "왓챠",
    "Apple TV",
    "아마존 프라임 비디오",
    "씨네폭스",
]

GENRE_WORDS = [
    "영화", "드라마", "예능", "애니메이션", "다큐멘터리", "시리즈",
    "키즈", "교양", "멜로/로맨스", "판타지", "액션", "코미디",
    "스릴러", "공포", "SF", "가족", "범죄", "미스터리",
]

BAD_TITLE_WORDS = {
    "오늘 공개", "내일 공개", "공개 예정", "공개 예정작",
    "종료 예정작", "신작", "예정작 & 신작", "전체",
    "홈", "랭킹", "바로 보기", "찜하기", "보는중", "봤어요",
    "공유하기", "좋아요", "별로예요",
}


def norm(s) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("\u00a0", " ")).strip()


def normalize_url(url: str) -> str:
    url = norm(url)
    if not url:
        return ""
    return urljoin(BASE_URL, url)


def parse_release_date(text: str, today: date) -> str:
    t = norm(text)

    if "오늘 공개" in t or t == "오늘":
        return today.isoformat()

    if "내일 공개" in t or t == "내일":
        return (today + timedelta(days=1)).isoformat()

    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", t)
    if m:
        mo, d = map(int, m.groups())
        try:
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=45):
                dt = date(today.year + 1, mo, d)
            return dt.isoformat()
        except ValueError:
            pass

    m = re.search(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?!\d)", t)
    if m:
        mo, d = map(int, m.groups())
        try:
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=45):
                dt = date(today.year + 1, mo, d)
            return dt.isoformat()
        except ValueError:
            pass

    return ""


def clean_title(title: str) -> str:
    title = norm(title)
    title = re.sub(r"\s*다시보기.*$", "", title)
    title = re.sub(r"\s*\|\s*키노라이츠.*$", "", title)
    title = re.sub(r"\s*-\s*키노라이츠.*$", "", title)
    title = re.sub(r"\s*#리뷰.*$", "", title)
    return norm(title)


def is_bad_title(title: str) -> bool:
    t = norm(title)

    if not t:
        return True

    if t in BAD_TITLE_WORDS:
        return True

    if t in PROVIDERS:
        return True

    if t in GENRE_WORDS:
        return True

    if re.fullmatch(r"\d+", t):
        return True

    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", t):
        return True

    if "공개" in t and len(t) <= 12:
        return True

    if "대표:" in t or "사업자등록번호" in t or "All rights reserved" in t:
        return True

    return False


def extract_genre(text: str) -> str:
    t = norm(text)
    for g in ["영화", "드라마", "예능", "애니메이션", "다큐멘터리", "시리즈"]:
        if g in t:
            return g
    for g in GENRE_WORDS:
        if g in t:
            return g
    return ""


def click_visible_text(page, label: str, exact: bool = True, timeout_ms: int = 3000) -> bool:
    try:
        loc = page.get_by_text(label, exact=exact)
        count = min(loc.count(), 20)

        for i in range(count):
            item = loc.nth(i)
            try:
                if item.is_visible(timeout=500):
                    item.click(timeout=timeout_ms)
                    page.wait_for_timeout(900)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def wait_and_scroll(page, max_scrolls: int = 12) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(1200)

    last_height = 0
    stable = 0

    for _ in range(max_scrolls):
        height = page.evaluate("() => document.body.scrollHeight")
        page.mouse.wheel(0, 2800)
        page.wait_for_timeout(800)
        new_height = page.evaluate("() => document.body.scrollHeight")

        if new_height == height or new_height == last_height:
            stable += 1
        else:
            stable = 0

        last_height = new_height

        if stable >= 3:
            break

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def extract_list_items(page, provider: str, today: date) -> list[dict[str, str]]:
    js = """
    () => {
      const anchors = Array.from(document.querySelectorAll('a[href]'));
      const out = [];
      const seen = new Set();

      for (const a of anchors) {
        const href = a.href || '';
        if (!href.includes('/season/') && !href.includes('/movie/') && !href.includes('/title/')) {
          continue;
        }

        let box = a;
        for (let i = 0; i < 4; i++) {
          if (box.parentElement) box = box.parentElement;
        }

        const img = a.querySelector('img') || box.querySelector('img');
        const text = (box.innerText || a.innerText || a.textContent || '').trim();
        const image_url = img ? (img.currentSrc || img.src || img.getAttribute('src') || '') : '';
        const img_alt = img ? (img.alt || img.getAttribute('alt') || '') : '';
        const aria = a.getAttribute('aria-label') || '';
        const title = a.getAttribute('title') || '';

        if (seen.has(href)) continue;
        seen.add(href);

        out.push({ href, text, image_url, img_alt, aria, title });
      }

      return out;
    }
    """

    raw_items = page.evaluate(js)
    rows = []

    for item in raw_items:
        text = norm(item.get("text", ""))
        url = normalize_url(item.get("href", ""))
        image_url = normalize_url(item.get("image_url", ""))

        release_date = parse_release_date(text, today)

        title = ""
        for cand in [item.get("img_alt", ""), item.get("aria", ""), item.get("title", "")]:
            cand = clean_title(cand)
            if not is_bad_title(cand):
                title = cand
                break

        rows.append(
            {
                "collect_date": today.isoformat(),
                "release_date": release_date,
                "title": title,
                "provider": provider,
                "genre": extract_genre(text),
                "url": url,
                "image_url": image_url,
                "_raw_text": text,
            }
        )

    return rows


def enrich_title_from_detail(page, row: dict[str, str], cache: dict[str, dict[str, str]]) -> dict[str, str]:
    url = row.get("url", "")

    if not url:
        return row

    if url in cache:
        detail = cache[url]
    else:
        detail = {"title": "", "genre": "", "image_url": ""}

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1200)

            body_text = page.locator("body").inner_text(timeout=5000)

            data = page.evaluate(
                """
                () => {
                  const meta = (sel) => document.querySelector(sel)?.getAttribute('content') || '';
                  const h1 = document.querySelector('h1')?.innerText || '';
                  const h2 = document.querySelector('h2')?.innerText || '';
                  const img = document.querySelector('img');
                  return {
                    document_title: document.title || '',
                    og_title: meta('meta[property="og:title"]'),
                    twitter_title: meta('meta[name="twitter:title"]'),
                    h1,
                    h2,
                    og_image: meta('meta[property="og:image"]'),
                    first_img: img ? (img.currentSrc || img.src || img.getAttribute('src') || '') : ''
                  };
                }
                """
            )

            title = ""
            for cand in [
                data.get("h1", ""),
                data.get("og_title", ""),
                data.get("twitter_title", ""),
                data.get("document_title", ""),
                data.get("h2", ""),
            ]:
                cand = clean_title(cand)
                if not is_bad_title(cand):
                    title = cand
                    break

            detail = {
                "title": title,
                "genre": extract_genre(body_text),
                "image_url": normalize_url(data.get("og_image") or data.get("first_img") or ""),
            }

        except Exception as e:
            print(f"[WARN] detail failed: {url} / {e}")

        cache[url] = detail

    if is_bad_title(row.get("title", "")) and detail.get("title"):
        row["title"] = detail["title"]

    if not row.get("genre") and detail.get("genre"):
        row["genre"] = detail["genre"]

    if not row.get("image_url") and detail.get("image_url"):
        row["image_url"] = detail["image_url"]

    return row


def collect_provider(context, provider: str, today: date, detail_cache: dict[str, dict[str, str]]):
    page = context.new_page()
    page.set_default_timeout(12000)

    print(f"[OPEN] {TARGET_URL} / {provider}")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    click_visible_text(page, "공개 예정작", exact=True)

    clicked = click_visible_text(page, provider, exact=True)
    if not clicked:
        print(f"[WARN] provider click failed: {provider}")

    wait_and_scroll(page)

    body_text = page.locator("body").inner_text(timeout=5000)
    rows = extract_list_items(page, provider, today)

    detail_page = context.new_page()
    detail_page.set_default_timeout(12000)

    enriched = []

    for row in rows:
        row = enrich_title_from_detail(detail_page, row, detail_cache)

        if not row.get("url"):
            continue

        if not row.get("release_date"):
            continue

        if is_bad_title(row.get("title", "")):
            continue

        enriched.append({c: norm(row.get(c, "")) for c in COLUMNS})

    detail_page.close()
    page.close()

    return enriched, body_text


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []

    for r in rows:
        key = (norm(r.get("provider")), norm(r.get("url")))

        if key in seen:
            continue

        seen.add(key)
        result.append({c: norm(r.get(c, "")) for c in COLUMNS})

    return result


def save_debug(rows: list[dict[str, str]], debug_text: str) -> None:
    DEBUG_TEXT.write_text(debug_text, encoding="utf-8")

    with DEBUG_CARDS.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in COLUMNS})


def existing_csv_has_rows(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return len(pd.read_csv(path)) > 0
    except Exception:
        return False


def write_csv_safely(rows: list[dict[str, str]]) -> None:
    rows = dedupe_rows(rows)
    df = pd.DataFrame(rows, columns=COLUMNS)

    if not df.empty:
        today_str = date.today().isoformat()
        df["release_date"] = df["release_date"].fillna("").astype(str)

        # 공개예정작만 남김: 오늘 이후만
        df = df[df["release_date"] >= today_str]

        # 제목 오류 제거
        df = df[~df["title"].isin(["오늘 공개", "내일 공개", "공개 예정", "공개 예정작"])]

    if df.empty:
        print("[ERROR] 공개예정작 유효 데이터 0건입니다.")
        print("[KEEP] 기존 CSV 유지")

        if existing_csv_has_rows(OUT_CSV):
            return

        pd.DataFrame(columns=COLUMNS).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
        sys.exit(1)

    df["_sort_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = (
        df.sort_values(["_sort_date", "provider", "title"], na_position="last")
        .drop(columns=["_sort_date"])
    )

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[OK] {OUT_CSV} 저장 완료: {len(df)} rows")


def main() -> None:
    today = date.today()
    all_rows = []
    debug_chunks = []
    detail_cache = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context = browser.new_context(
            viewport={"width": 390, "height": 1300},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )

        for provider in PROVIDERS:
            rows, text = collect_provider(context, provider, today, detail_cache)
            print(f"[COLLECT] {provider}: {len(rows)} rows")
            all_rows.extend(rows)
            debug_chunks.append(f"\n\n===== {provider} / rows={len(rows)} =====\n{text}")

        try:
            page = context.new_page()
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            page.screenshot(path=str(DEBUG_SCREENSHOT), full_page=True)
            page.close()
        except Exception:
            pass

        context.close()
        browser.close()

    save_debug(all_rows, "".join(debug_chunks))
    write_csv_safely(all_rows)


if __name__ == "__main__":
    main()

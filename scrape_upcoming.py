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

    if "오늘 공개" in t:
        return today.isoformat()

    if "내일 공개" in t:
        return (today + timedelta(days=1)).isoformat()

    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*공개", t)
    if m:
        mo, d = map(int, m.groups())
        try:
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=45):
                dt = date(today.year + 1, mo, d)
            return dt.isoformat()
        except ValueError:
            return ""

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


def click_upcoming_tab(page) -> None:
    try:
        page.get_by_text("공개 예정작", exact=True).first.click(timeout=5000)
        page.wait_for_timeout(1200)
    except Exception:
        pass


def click_provider_filter(page, provider: str) -> bool:
    labels = {
        "디즈니+": ["디즈니+", "디즈니 플러스", "Disney+"],
        "왓챠": ["왓챠", "Watcha"],
        "Apple TV": ["Apple TV", "Apple TV+"],
        "아마존 프라임 비디오": ["아마존", "프라임", "Prime"],
    }.get(provider, [provider])

    try:
        ok = page.evaluate(
            """
            async (labels) => {
              const sleep = ms => new Promise(r => setTimeout(r, ms));

              for (let step = 0; step < 30; step++) {
                const els = Array.from(document.querySelectorAll('button, a, div, span'));

                for (const label of labels) {
                  const target = els.find(el => {
                    const txt = (el.innerText || el.textContent || '').trim();
                    return txt === label || txt.includes(label);
                  });

                  if (target) {
                    const clickable = target.closest('button, a, [role="button"]') || target;
                    clickable.scrollIntoView({block:'center', inline:'center'});
                    await sleep(300);

                    clickable.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                    clickable.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                    clickable.dispatchEvent(new MouseEvent('click', {bubbles:true}));

                    await sleep(1800);
                    return true;
                  }
                }

                const horizontals = Array.from(document.querySelectorAll('*')).filter(el => {
                  const s = window.getComputedStyle(el);
                  return el.scrollWidth > el.clientWidth + 30 &&
                    (s.overflowX === 'auto' || s.overflowX === 'scroll');
                });

                for (const h of horizontals) {
                  h.scrollLeft += 250;
                }

                await sleep(300);
              }

              return false;
            }
            """,
            labels,
        )
        return bool(ok)

    except Exception:
        return False


def smart_scroll_all(page, max_rounds: int = 90) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(1500)

    last_count = 0
    stable = 0

    for i in range(max_rounds):
        result = page.evaluate(
            """
            () => {
              const els = Array.from(document.querySelectorAll('*'));

              const scrollables = els.filter(el => {
                const s = window.getComputedStyle(el);
                return (
                  (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
                  el.scrollHeight > el.clientHeight + 50
                );
              });

              window.scrollTo(0, document.body.scrollHeight);

              for (const el of scrollables) {
                el.scrollTop = el.scrollHeight;
              }

              const links = Array.from(document.querySelectorAll('a[href]'))
                .filter(a => {
                  const href = a.href || '';
                  return href.includes('/season/') || href.includes('/movie/') || href.includes('/title/');
                })
                .length;

              return { links, scrollables: scrollables.length };
            }
            """
        )

        count = int(result.get("links", 0))
        print(f"[SCROLL] round={i+1} links={count} scrollables={result.get('scrollables')}")

        page.wait_for_timeout(900)

        if count <= last_count:
            stable += 1
        else:
            stable = 0

        last_count = count

        if stable >= 10:
            break


def extract_list_items(page, today: date, provider: str) -> list[dict[str, str]]:
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
        for (let i = 0; i < 5; i++) {
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
        release_date = parse_release_date(text, today)

        if not release_date:
            continue

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
                "url": normalize_url(item.get("href", "")),
                "image_url": normalize_url(item.get("image_url", "")),
                "_raw_text": text,
            }
        )

    return rows


def enrich_title_from_detail(page, row: dict[str, str], cache: dict[str, dict]) -> dict[str, str]:
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

            body_text = page.locator("body").inner_text(timeout=6000)

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


def collect_page(context, today: date, provider: str) -> tuple[list[dict[str, str]], str]:
    page = context.new_page()
    page.set_default_timeout(15000)

    print(f"[OPEN] {TARGET_URL} / provider={provider}")

    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1800)

    click_upcoming_tab(page)

    if provider != "전체":
        clicked = click_provider_filter(page, provider)
        print(f"[FILTER] {provider} clicked={clicked}")

        if not clicked:
            page.close()
            return [], ""

        page.wait_for_timeout(2500)

    smart_scroll_all(page)

    try:
        body_text = page.locator("body").inner_text(timeout=6000)
    except Exception:
        body_text = ""

    if provider == "전체":
        try:
            page.screenshot(path=str(DEBUG_SCREENSHOT), full_page=True)
        except Exception:
            pass

    rows = extract_list_items(page, today, provider)
    print(f"[LIST] {provider}: {len(rows)} rows")

    page.close()
    return rows, body_text


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []

    for r in rows:
        key = (
            norm(r.get("release_date")),
            norm(r.get("title")),
            norm(r.get("provider")),
            norm(r.get("url")),
        )

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

        df = df[df["release_date"] >= today_str]
        df = df[~df["title"].isin(["오늘 공개", "내일 공개", "공개 예정", "공개 예정작"])]
        df = df[df["title"].fillna("").astype(str).str.len() > 0]

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
    detail_cache = {}
    all_rows = []
    debug_chunks = []

    targets = ["전체"] + PROVIDERS

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
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

        detail_page = context.new_page()
        detail_page.set_default_timeout(15000)

        for provider in targets:
            rows, body_text = collect_page(context, today, provider)

            fixed_rows = []
            for row in rows:
                row = enrich_title_from_detail(detail_page, row, detail_cache)
                if not is_bad_title(row.get("title", "")):
                    fixed_rows.append(row)

            print(f"[COLLECT] {provider}: {len(fixed_rows)} rows")
            all_rows.extend(fixed_rows)
            debug_chunks.append(f"\n\n===== {provider} / rows={len(fixed_rows)} =====\n{body_text}")

        detail_page.close()
        context.close()
        browser.close()

    save_debug(all_rows, "".join(debug_chunks))
    write_csv_safely(all_rows)


if __name__ == "__main__":
    main()

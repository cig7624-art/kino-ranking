# -*- coding: utf-8 -*-
"""
KinoLights 공개 예정작 수집기
- requests/BeautifulSoup 방식 대신 Playwright로 실제 브라우저 렌더링 후 수집
- 출력: upcoming_releases.csv
- 디버그: debug_upcoming_text.txt, debug_upcoming_cards.csv
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
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
    "영화",
    "드라마",
    "예능",
    "애니메이션",
    "다큐멘터리",
    "시리즈",
    "키즈",
    "교양",
    "방송",
]

BAD_TITLE_WORDS = set(
    [
        "홈",
        "랭킹",
        "예정작 & 신작",
        "종료 예정작",
        "공개 예정작",
        "신작",
        "전체",
        "이용약관",
        "개인정보처리방침",
        "고객센터",
        "광고문의",
        "제휴문의",
        "App Store",
        "Play Store",
    ]
    + PROVIDERS
)


def norm(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("\u00a0", " ")).strip()


def visible_lines(text: str) -> list[str]:
    lines = []
    for raw in str(text).splitlines():
        line = norm(raw)
        if line:
            lines.append(line)
    return lines


def normalize_url(url: str) -> str:
    url = norm(url)
    if not url:
        return ""
    return urljoin(BASE_URL, url)


def parse_release_date(text: str, today: date) -> str:
    t = norm(text)

    m = re.search(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?", t)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            pass

    m = re.search(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일", t)
    if m:
        mo, d = map(int, m.groups())
        try:
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=45):
                dt = date(today.year + 1, mo, d)
            return dt.isoformat()
        except ValueError:
            pass

    m = re.search(r"(?<!\d)(\d{1,2})\s*[./]\s*(\d{1,2})(?!\d)", t)
    if m:
        mo, d = map(int, m.groups())
        try:
            dt = date(today.year, mo, d)
            if dt < today - timedelta(days=45):
                dt = date(today.year + 1, mo, d)
            return dt.isoformat()
        except ValueError:
            pass

    if "오늘" in t:
        return today.isoformat()
    if "내일" in t:
        return (today + timedelta(days=1)).isoformat()

    return ""


def extract_genre(lines: list[str]) -> str:
    for line in lines:
        for part in re.split(r"[·|/•,]", line):
            part = norm(part)
            if part in GENRE_WORDS:
                return part
            for g in GENRE_WORDS:
                if re.fullmatch(rf".*\b{re.escape(g)}\b.*", part):
                    return g
    return ""


def is_bad_title_line(line: str) -> bool:
    s = norm(line)
    if not s:
        return True
    if s in BAD_TITLE_WORDS:
        return True
    if s in GENRE_WORDS:
        return True
    if re.fullmatch(r"\d+", s):
        return True
    if re.fullmatch(r"20\d{2}", s):
        return True
    if re.search(r"\d{1,3}(\.\d)?\s*%", s):
        return True
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", s):
        return True
    if re.search(r"20\d{2}\s*[.\-/년]", s):
        return True
    if re.search(r"\bD\s*[-+]?\s*\d+\b", s, re.I):
        return True
    if "대표:" in s or "사업자등록번호" in s or "All rights reserved" in s:
        return True
    if any(g in s for g in GENRE_WORDS) and ("·" in s or "20" in s):
        return True
    return False


def extract_title(lines: list[str]) -> str:
    candidates = []
    for line in lines:
        s = norm(line)
        if is_bad_title_line(s):
            continue
        if len(s) > 80:
            continue
        if any(p == s for p in PROVIDERS):
            continue
        candidates.append(s)

    if not candidates:
        return ""

    return candidates[0]


def parse_card(raw: dict[str, str], provider: str, today: date) -> dict[str, str] | None:
    text = raw.get("text", "")
    lines = visible_lines(text)
    title = extract_title(lines)
    release_date = parse_release_date(text, today)
    genre = extract_genre(lines)

    if not title:
        return None

    if title in BAD_TITLE_WORDS or len(title) < 1:
        return None

    if not (raw.get("href") or raw.get("image_url") or release_date or genre):
        return None

    return {
        "collect_date": today.isoformat(),
        "release_date": release_date,
        "title": title,
        "provider": provider,
        "genre": genre,
        "url": normalize_url(raw.get("href", "")),
        "image_url": normalize_url(raw.get("image_url", "")),
    }


def click_visible_text(page, label: str, timeout_ms: int = 3000) -> bool:
    try:
        loc = page.get_by_text(label, exact=True)
        count = min(loc.count(), 20)
        for i in range(count):
            item = loc.nth(i)
            try:
                if item.is_visible(timeout=500):
                    item.click(timeout=timeout_ms)
                    page.wait_for_timeout(800)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def wait_and_scroll(page, max_scrolls: int = 10) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(1200)

    stable = 0
    last_height = 0

    for _ in range(max_scrolls):
        height = page.evaluate("() => document.body.scrollHeight")
        page.mouse.wheel(0, 2800)
        page.wait_for_timeout(700)
        new_height = page.evaluate("() => document.body.scrollHeight")

        if new_height == last_height or new_height == height:
            stable += 1
        else:
            stable = 0

        last_height = new_height

        if stable >= 3:
            break

    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def extract_dom_candidates(page) -> list[dict[str, str]]:
    js = r"""
    () => {
      const isVisible = (el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style && style.display !== 'none' && style.visibility !== 'hidden'
          && rect.width >= 40 && rect.height >= 24;
      };

      const pickText = (el) => (el.innerText || el.textContent || '').trim();

      const nodes = Array.from(document.querySelectorAll(
        'a[href], article, li, [role="listitem"], [data-testid*="card"], div[class*="card"], div[class*="Card"], div[class*="item"], div[class*="Item"]'
      ));

      const out = [];
      const seen = new Set();

      for (const el of nodes) {
        if (!isVisible(el)) continue;

        const text = pickText(el);
        if (!text || text.length < 2 || text.length > 1200) continue;

        const a = el.matches('a[href]') ? el : el.querySelector('a[href]');
        const img = el.querySelector('img');

        const href = a ? a.href : '';
        const image_url = img ? (img.currentSrc || img.src || img.getAttribute('src') || '') : '';

        const key = (href + '|' + text.replace(/\s+/g, ' ')).slice(0, 500);
        if (seen.has(key)) continue;
        seen.add(key);

        out.push({
          text,
          href,
          image_url,
          tag: el.tagName,
          class_name: String(el.className || '').slice(0, 200)
        });
      }

      return out;
    }
    """

    try:
        return page.evaluate(js)
    except Exception as e:
        print(f"[WARN] DOM extraction failed: {e}")
        return []


def collect_one_provider(page, provider: str, today: date) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)

    clicked = click_visible_text(page, provider)
    if not clicked:
        print(f"[WARN] provider click failed: {provider}")

    wait_and_scroll(page)

    body_text = ""
    try:
        body_text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        pass

    raw_cards = extract_dom_candidates(page)

    rows: list[dict[str, str]] = []
    for raw in raw_cards:
        parsed = parse_card(raw, provider, today)
        if parsed:
            rows.append(parsed)

    return rows, raw_cards, body_text


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


def save_debug(raw_cards: list[dict[str, str]], debug_text: str) -> None:
    DEBUG_TEXT.write_text(debug_text, encoding="utf-8")

    with DEBUG_CARDS.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["provider", "text", "href", "image_url", "tag", "class_name"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for c in raw_cards:
            writer.writerow({k: c.get(k, "") for k in fieldnames})


def existing_csv_has_rows(path: Path) -> bool:
    if not path.exists():
        return False

    try:
        df = pd.read_csv(path)
        return len(df) > 0
    except Exception:
        return False


def write_csv_safely(rows: list[dict[str, str]], out_csv: Path = OUT_CSV) -> None:
    rows = dedupe_rows(rows)
    df = pd.DataFrame(rows, columns=COLUMNS)

    if df.empty:
        print("[ERROR] 공개예정작을 0건 수집했습니다.")
        print("[ERROR] debug_upcoming_text.txt / debug_upcoming_cards.csv를 확인하세요.")

        if existing_csv_has_rows(out_csv):
            print(f"[KEEP] 기존 {out_csv}에 데이터가 있어 덮어쓰지 않았습니다.")
            return

        pd.DataFrame(columns=COLUMNS).to_csv(out_csv, index=False, encoding="utf-8-sig")
        sys.exit(1)

    df["_sort_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = (
        df.sort_values(["_sort_date", "provider", "title"], na_position="last")
        .drop(columns=["_sort_date"])
    )

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] {out_csv} 저장 완료: {len(df)} rows")


def main() -> None:
    today = date.today()

    all_rows: list[dict[str, str]] = []
    all_raw_cards: list[dict[str, str]] = []
    debug_chunks: list[str] = []

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

        page = context.new_page()
        page.set_default_timeout(12000)

        print(f"[OPEN] {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)

        click_visible_text(page, "공개 예정작")
        page.wait_for_timeout(1000)

        for provider in PROVIDERS:
            print(f"[COLLECT] {provider}")

            rows, raw_cards, body_text = collect_one_provider(page, provider, today)

            all_rows.extend(rows)

            for c in raw_cards:
                c["provider"] = provider

            all_raw_cards.extend(raw_cards)
            debug_chunks.append(
                f"\n\n===== PROVIDER: {provider} / rows={len(rows)} =====\n{body_text}"
            )

        try:
            page.screenshot(path=str(DEBUG_SCREENSHOT), full_page=True)
        except Exception:
            pass

        context.close()
        browser.close()

    save_debug(all_raw_cards, "".join(debug_chunks))
    write_csv_safely(all_rows, OUT_CSV)


if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
import requests
import re
import difflib
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="키노라이츠 랭킹/OTT 검색",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background:#090d1a; }
h1,h2,h3,p,label,div,span { color:#f8fafc !important; }
.block-container { padding-top:1.3rem; }

.metric {
    background:#111827;
    border:1px solid #263244;
    border-radius:16px;
    padding:14px 16px;
    min-height:72px;
}
.metric-title {
    color:#94a3b8 !important;
    font-size:13px;
    margin-bottom:6px;
}
.metric-text {
    color:#f8fafc !important;
    font-size:18px;
    font-weight:800;
}

.rank-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:8px 10px;
    margin-bottom:7px;
    display:flex;
    align-items:center;
    justify-content:space-between;
}
.rank-left {
    display:flex;
    align-items:center;
    gap:10px;
}
.rank-num {
    font-size:17px;
    font-weight:900;
    color:#f8fafc !important;
    min-width:30px;
    text-align:right;
    font-style:italic;
}
.title {
    font-size:15px;
    font-weight:800;
}
.meta {
    color:#64748b !important;
    font-size:12px;
    margin-top:3px;
}
.badge-new { color:#f97316 !important; font-weight:900; font-size:13px; }
.badge-up { color:#22c55e !important; font-weight:900; font-size:13px; }
.badge-down { color:#ef4444 !important; font-weight:900; font-size:13px; }

.side-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:12px;
    padding:9px 11px;
    margin-bottom:8px;
}
.small { color:#94a3b8 !important; font-size:12px; }

.ott-badge{
    display:inline-block;
    background:#1e293b;
    border:1px solid #475569;
    border-radius:999px;
    padding:5px 10px;
    margin-right:6px;
    margin-top:6px;
    font-weight:700;
}

.filter-note {
    color:#94a3b8 !important;
    font-size:12px;
    margin-top:2px;
    margin-bottom:10px;
}

[data-baseweb="select"] * { color:#111827 !important; }
[data-baseweb="popover"] * {
    color:#111827 !important;
    background:#ffffff !important;
}
[data-baseweb="checkbox"] * {
    color:#f8fafc !important;
}
input { color:#111827 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎬 키노라이츠 랭킹 / OTT 편성 검색</h1>", unsafe_allow_html=True)

OTT_NAMES = [
    "넷플릭스", "티빙", "웨이브", "디즈니+",
    "쿠팡플레이", "왓챠", "애플TV+", "라프텔"
]

SHEET_ID = "13_ULv4lXt2UPugaom5daL9ycV8COG7tD7bzmDT3WIwA"


def normalize_title(title):
    if title is None:
        return ""

    try:
        if pd.isna(title):
            return ""
    except Exception:
        pass

    title = str(title).strip().lower()
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"[^0-9a-zA-Z가-힣]", "", title)

    return title


def safe_cell_value(value):
    if isinstance(value, pd.Series):
        for v in value.tolist():
            if str(v).strip() not in ["", "nan", "NaN", "None"]:
                return v
        return ""

    if isinstance(value, list):
        for v in value:
            if str(v).strip() not in ["", "nan", "NaN", "None"]:
                return v
        return ""

    return value


def is_date_like(value):
    value = safe_cell_value(value)

    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    text = str(value).strip()

    if text == "":
        return False

    if text.upper() in ["X", "O"]:
        return False

    if text in ["-", "없음", "미정", "nan", "NaN", "None"]:
        return False

    # 엑셀 시리얼 날짜: 45700 또는 45700.0
    if re.fullmatch(r"\d{5}(\.0)?", text):
        return True

    date_patterns = [
        r"\d{4}[-./]\d{1,2}[-./]\d{1,2}",
        r"\d{2}[-./]\d{1,2}[-./]\d{1,2}",
        r"\d{1,2}월\s*\d{1,2}일",
        r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일",
    ]

    for pattern in date_patterns:
        if re.search(pattern, text):
            return True

    parsed = pd.to_datetime(text, errors="coerce")

    if pd.isna(parsed):
        return False

    return True


@st.cache_data(ttl=3600)
def load_google_sheet_raw(sheet_name):
    encoded_sheet = quote(sheet_name)
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    )

    return pd.read_csv(url, header=None, dtype=str).fillna("")


def get_col_value(row, col_index):
    try:
        return safe_cell_value(row.iloc[col_index])
    except Exception:
        return ""


def add_btv_title(rows, title, category, source_sheet, btv_date=""):
    title = safe_cell_value(title)
    title_text = str(title).strip()

    if title_text == "":
        return

    title_norm = normalize_title(title_text)

    if title_norm == "":
        return

    rows.append({
        "title_norm": title_norm,
        "btv_title": title_text,
        "btv_plus_category": category,
        "btv_genre": category,
        "btv_plus_date": str(btv_date).strip(),
        "btv_source_sheet": source_sheet,
    })


@st.cache_data(ttl=3600)
def load_btv_plus_titles():
    rows = []

    # 콘텐츠라인업: D열 타이틀, F열 날짜
    # D열 index = 3, F열 index = 5
    lineup_sheet_candidates = [
        "콘텐츠라인업",
        "콘텐츠 라인업",
        "콘텐츠 Line-up",
        "라인업",
    ]

    for sheet_name in lineup_sheet_candidates:
        try:
            raw = load_google_sheet_raw(sheet_name)
        except Exception:
            continue

        if raw.empty:
            continue

        for _, row in raw.iterrows():
            title = get_col_value(row, 3)
            btv_date = get_col_value(row, 5)

            if str(title).strip() == "":
                continue

            if not is_date_like(btv_date):
                continue

            add_btv_title(
                rows=rows,
                title=title,
                category="콘텐츠라인업",
                source_sheet=sheet_name,
                btv_date=btv_date
            )

        break

    # 영화 / 해외드라마 / 애니메이션(25'1~): C열 타이틀
    # C열 index = 2
    c_col_sheets = [
        ("영화", "영화"),
        ("해외드라마", "해외드라마"),
        ("애니메이션(25'1~)", "애니메이션"),
        ("애니메이션 (25'1~)", "애니메이션"),
    ]

    loaded_c_sheet_names = set()

    for sheet_name, category in c_col_sheets:
        if category in loaded_c_sheet_names and category == "애니메이션":
            continue

        try:
            raw = load_google_sheet_raw(sheet_name)
        except Exception:
            continue

        if raw.empty:
            continue

        for _, row in raw.iterrows():
            title = get_col_value(row, 2)

            if str(title).strip() == "":
                continue

            add_btv_title(
                rows=rows,
                title=title,
                category=category,
                source_sheet=sheet_name,
                btv_date=""
            )

        loaded_c_sheet_names.add(category)

    # 키즈: F열 타이틀
    # F열 index = 5
    kids_sheet_candidates = [
        "키즈",
        "Kids",
    ]

    for sheet_name in kids_sheet_candidates:
        try:
            raw = load_google_sheet_raw(sheet_name)
        except Exception:
            continue

        if raw.empty:
            continue

        for _, row in raw.iterrows():
            title = get_col_value(row, 5)

            if str(title).strip() == "":
                continue

            add_btv_title(
                rows=rows,
                title=title,
                category="키즈",
                source_sheet=sheet_name,
                btv_date=""
            )

        break

    if not rows:
        return pd.DataFrame(
            columns=[
                "title_norm",
                "btv_title",
                "btv_plus_category",
                "btv_genre",
                "btv_plus_date",
                "btv_source_sheet",
            ]
        )

    btv_df = pd.DataFrame(rows).fillna("")
    btv_df = btv_df[btv_df["title_norm"] != ""].copy()

    remove_words = [
        "타이틀명",
        "콘텐츠명",
        "제목",
        "title",
        "방송명",
        "프로그램명",
        "편성일자",
        "btv편성일자",
        "btv편성",
    ]

    btv_df = btv_df[
        ~btv_df["title_norm"].isin([normalize_title(w) for w in remove_words])
    ].copy()

    btv_df["has_btv_date"] = btv_df["btv_plus_date"].astype(str).str.strip() != ""

    btv_df = (
        btv_df
        .sort_values(["title_norm", "has_btv_date"], ascending=[True, False])
        .drop_duplicates("title_norm", keep="first")
        .drop(columns=["has_btv_date"])
    )

    return btv_df


def find_btv_match_info(kino_title, btv_df):
    kino_norm = normalize_title(kino_title)

    default = {
        "is_btv_plus": False,
        "btv_title": "",
        "btv_plus_category": "",
        "btv_genre": "",
        "btv_plus_date": "",
        "btv_source_sheet": "",
        "btv_match_score": 0.0,
        "btv_match_type": "",
    }

    if kino_norm == "" or btv_df.empty:
        return default

    # 1차: 완전일치
    exact = btv_df[btv_df["title_norm"] == kino_norm]

    if not exact.empty:
        row = exact.iloc[0]

        return {
            "is_btv_plus": True,
            "btv_title": row.get("btv_title", ""),
            "btv_plus_category": row.get("btv_plus_category", ""),
            "btv_genre": row.get("btv_genre", ""),
            "btv_plus_date": row.get("btv_plus_date", ""),
            "btv_source_sheet": row.get("btv_source_sheet", ""),
            "btv_match_score": 1.0,
            "btv_match_type": "exact",
        }

    best_row = None
    best_score = 0.0
    best_type = ""

    # 2차: 포함관계
    for _, row in btv_df.iterrows():
        btv_norm = str(row.get("title_norm", ""))

        if len(kino_norm) < 4 or len(btv_norm) < 4:
            continue

        if kino_norm in btv_norm or btv_norm in kino_norm:
            shorter = min(len(kino_norm), len(btv_norm))
            longer = max(len(kino_norm), len(btv_norm))
            score = shorter / longer

            if score > best_score:
                best_score = score
                best_row = row
                best_type = "contains"

    if best_row is not None and best_score >= 0.62:
        return {
            "is_btv_plus": True,
            "btv_title": best_row.get("btv_title", ""),
            "btv_plus_category": best_row.get("btv_plus_category", ""),
            "btv_genre": best_row.get("btv_genre", ""),
            "btv_plus_date": best_row.get("btv_plus_date", ""),
            "btv_source_sheet": best_row.get("btv_source_sheet", ""),
            "btv_match_score": round(best_score, 3),
            "btv_match_type": best_type,
        }

    # 3차: 유사도 매칭
    for _, row in btv_df.iterrows():
        btv_norm = str(row.get("title_norm", ""))

        if len(kino_norm) < 4 or len(btv_norm) < 4:
            continue

        score = difflib.SequenceMatcher(None, kino_norm, btv_norm).ratio()

        if score > best_score:
            best_score = score
            best_row = row
            best_type = "similar"

    if best_row is not None and best_score >= 0.86:
        return {
            "is_btv_plus": True,
            "btv_title": best_row.get("btv_title", ""),
            "btv_plus_category": best_row.get("btv_plus_category", ""),
            "btv_genre": best_row.get("btv_genre", ""),
            "btv_plus_date": best_row.get("btv_plus_date", ""),
            "btv_source_sheet": best_row.get("btv_source_sheet", ""),
            "btv_match_score": round(best_score, 3),
            "btv_match_type": best_type,
        }

    return default


def attach_btv_plus_flag(df):
    df = df.copy()

    try:
        btv_df = load_btv_plus_titles()
    except Exception as e:
        st.warning(f"B tv+ 편성작 구글시트 로드 실패: {e}")
        df["is_btv_plus"] = False
        return df

    if df.empty or btv_df.empty:
        df["is_btv_plus"] = False
        df["btv_title"] = ""
        df["btv_plus_category"] = ""
        df["btv_genre"] = ""
        df["btv_plus_date"] = ""
        df["btv_source_sheet"] = ""
        df["btv_match_score"] = 0.0
        df["btv_match_type"] = ""
        return df

    if "title" not in df.columns:
        df["is_btv_plus"] = False
        return df

    match_rows = []

    # 여기서부터는 이미 최신일자/기간/OTT까지 줄인 base에만 적용됨
    for _, row in df.iterrows():
        match_rows.append(find_btv_match_info(row.get("title", ""), btv_df))

    match_df = pd.DataFrame(match_rows)

    df = pd.concat([df.reset_index(drop=True), match_df.reset_index(drop=True)], axis=1)

    return df


def search_contents(keyword):
    query = """
    query SearchContents($keyword: String!) {
      contents(keyword: $keyword, limit: 5) {
        id
        titleKr
        openYear
      }
    }
    """

    payload = {
        "operationName": "SearchContents",
        "variables": {"keyword": keyword},
        "query": query,
    }

    res = requests.post(
        "https://gateway.kinolights.com/graphql",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=20,
    )

    data = res.json()

    if "errors" in data:
        return []

    return data["data"]["contents"]


def get_ott_providers(content_id):
    urls = [
        f"https://m.kinolights.com/title/{content_id}",
        f"https://m.kinolights.com/content/{content_id}",
        f"https://m.kinolights.com/contents/{content_id}",
    ]

    found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium"
        )

        page = browser.new_page(
            viewport={"width": 430, "height": 1600},
            user_agent="Mozilla/5.0"
        )

        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1200)

                text = page.locator("body").inner_text()

                if "보러가기" not in text:
                    continue

                section = text.split("보러가기", 1)[1]

                if "시청 주의 가이드" in section:
                    section = section.split("시청 주의 가이드", 1)[0]

                for ott in OTT_NAMES:
                    if ott in section:
                        found.append(ott)

                if found:
                    break

            except Exception:
                continue

        browser.close()

    return sorted(set(found))


def make_meta(row):
    media_type = str(row.get("media_type", "")).upper()
    genres = str(row.get("genres", "")).replace(",", "/")
    open_year = str(row.get("open_year", ""))

    type_text = ""

    if media_type == "MOVIE":
        type_text = "영화"
    elif media_type in ["TV", "SHOW", "SERIES", "DRAMA"]:
        type_text = "드라마"
    elif media_type == "ANIMATION":
        type_text = "애니메이션"

    parts = []

    if type_text:
        parts.append(type_text)

    if genres and genres != "nan":
        parts.append(genres)

    if open_year and open_year != "nan":
        parts.append(open_year)

    return " · ".join(parts)


tab1, tab2 = st.tabs(["📈 랭킹 대시보드", "🔎 OTT 제공처 검색"])

with tab1:
    file = Path("ranking_history.csv")

    if not file.exists():
        st.error("ranking_history.csv가 없습니다. Actions에서 수집을 먼저 실행하세요.")
        st.stop()

    df = pd.read_csv(file)

    if df.empty:
        st.error("수집된 랭킹 데이터가 없습니다.")
        st.stop()

    for col in ["providers", "genres", "open_year", "media_type"]:
        if col not in df.columns:
            df[col] = ""

    df["date"] = df["date"].astype(str)
    df["period"] = df["period"].astype(str)
    df["title"] = df["title"].astype(str)
    df["providers"] = df["providers"].fillna("").astype(str)
    df["genres"] = df["genres"].fillna("").astype(str)
    df["open_year"] = df["open_year"].fillna("").astype(str)
    df["media_type"] = df["media_type"].fillna("").astype(str)
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["is_new"] = df["is_new"].astype(str).str.lower().isin(["true", "1"])

    latest_date = sorted(df["date"].unique(), reverse=True)[0]
    latest = df[df["date"] == latest_date].copy()

    top1, top2, top3 = st.columns([1, 1, 1])

    with top1:
        selected_period = st.selectbox(
            "기간 선택",
            ["일간", "주간", "월간"],
            index=1
        )

    with top2:
        selected_ott = st.selectbox(
            "OTT 선택",
            ["전체"] + OTT_NAMES,
            index=0
        )

    with top3:
        st.markdown(f"""
        <div class="metric">
            <div class="metric-title">기준일</div>
            <div class="metric-text">{latest_date}</div>
        </div>
        """, unsafe_allow_html=True)

    base = latest[latest["period"] == selected_period].copy()

    if selected_ott != "전체":
        base = base[base["providers"].str.contains(selected_ott, na=False)].copy()

    # 핵심 변경: 전체 df가 아니라 현재 조건 base에만 B tv+ 유사매칭 적용
    with st.spinner("B tv+ 편성작 매칭 중..."):
        base = attach_btv_plus_flag(base)

    btv_count = int(base["is_btv_plus"].sum()) if "is_btv_plus" in base.columns else 0
    total_count = len(base)

    only_btv_plus = st.checkbox(
        "B tv+ 편성작만 보기",
        value=False
    )

    st.markdown(
        f'<div class="filter-note">현재 조건 기준 B tv+ 매칭: {btv_count}개 / 전체 {total_count}개</div>',
        unsafe_allow_html=True
    )

    if only_btv_plus:
        base = base[base["is_btv_plus"] == True].copy()

    base = base.sort_values("rank")
    new_df = base[base["is_new"] == True].copy()
    up_df = base[base["delta"] > 0].copy().sort_values("delta", ascending=False)

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1.15, 1, 1])

    with col1:
        title_prefix = "B tv+ 편성작 " if only_btv_plus else ""
        st.subheader(f"🏆 {title_prefix}{selected_ott} {selected_period} TOP100")

        if base.empty:
            st.warning("데이터 없음")
        else:
            for _, row in base.head(100).iterrows():
                if row["is_new"]:
                    badge = '<span class="badge-new">NEW</span>'
                elif row["delta"] > 0:
                    badge = f'<span class="badge-up">▲{int(row["delta"])}</span>'
                elif row["delta"] < 0:
                    badge = f'<span class="badge-down">▼{abs(int(row["delta"]))}</span>'
                else:
                    badge = ""

                meta = make_meta(row)

                st.markdown(f"""
                <div class="rank-card">
                    <div class="rank-left">
                        <div class="rank-num">{int(row['rank'])}</div>
                        <div>
                            <div class="title">{row['title']}</div>
                            <div class="meta">{meta}</div>
                        </div>
                    </div>
                    <div>{badge}</div>
                </div>
                """, unsafe_allow_html=True)

    with col2:
        title_prefix = "B tv+ " if only_btv_plus else ""
        st.subheader(f"🚀 {title_prefix}급상승 콘텐츠")

        if up_df.empty:
            st.info("급상승 콘텐츠 없음")
        else:
            for _, row in up_df.head(30).iterrows():
                meta = make_meta(row)

                st.markdown(f"""
                <div class="side-card">
                    <span class="badge-up">▲{int(row['delta'])}</span>
                    &nbsp;
                    <b>{row['title']}</b><br>
                    <span class="small">#{int(row['rank'])} · {meta}</span>
                </div>
                """, unsafe_allow_html=True)

    with col3:
        title_prefix = "B tv+ " if only_btv_plus else ""
        st.subheader(f"🔥 {title_prefix}신규 진입 콘텐츠")

        if new_df.empty:
            st.info("신규 진입 콘텐츠 없음")
        else:
            for _, row in new_df.head(30).iterrows():
                meta = make_meta(row)

                st.markdown(f"""
                <div class="side-card">
                    <span class="badge-new">NEW</span>
                    &nbsp;
                    #{int(row['rank'])}
                    &nbsp;
                    <b>{row['title']}</b><br>
                    <span class="small">{meta}</span>
                </div>
                """, unsafe_allow_html=True)

with tab2:
    st.subheader("🔎 타이틀로 OTT 제공처 검색")

    keyword = st.text_input(
        "작품명을 입력하세요",
        placeholder="예: 멋진 신세계"
    )

    if keyword:
        with st.spinner("키노라이츠에서 정액제 제공처 확인 중..."):
            results = search_contents(keyword)

            if not results:
                st.warning("검색 결과 없음")
                st.stop()

            item = results[0]
            title = item.get("titleKr")
            open_year = item.get("openYear")
            content_id = item.get("id")

            providers = get_ott_providers(content_id)

            if providers:
                provider_html = "".join(
                    [f'<span class="ott-badge">{p}</span>' for p in providers]
                )
            else:
                provider_html = '<span class="small">정액제 OTT 없음</span>'

            st.markdown(f"""
            <div class="side-card">
                <h3>{title}</h3>
                <div class="small">연도: {open_year}</div>
                <div style="margin-top:10px;">{provider_html}</div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("다른 검색 후보 보기"):
                for other in results[1:]:
                    st.markdown(
                        f"- {other.get('titleKr')} ({other.get('openYear')})"
                    )

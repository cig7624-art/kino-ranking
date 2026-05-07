import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
    page_title="키노라이츠 랭킹 대시보드",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: #0f172a;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

h1, h2, h3, p, label, div, span {
    color: #f8fafc !important;
}

h1 {
    font-size: 36px !important;
    font-weight: 900 !important;
    margin-bottom: 2px !important;
}

.subtitle {
    color: #cbd5e1 !important;
    font-size: 15px;
    margin-bottom: 18px;
}

.metric-card {
    background: #1e293b;
    padding: 16px 18px;
    border-radius: 16px;
    border: 1px solid #334155;
    min-height: 95px;
}

.card-title {
    font-size: 14px;
    color: #cbd5e1 !important;
    margin-bottom: 6px;
}

.big-number {
    font-size: 30px;
    font-weight: 900;
    color: #38bdf8 !important;
}

.card-sub {
    font-size: 12px;
    color: #94a3b8 !important;
    margin-top: 3px;
}

.rank-card {
    background-color: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 7px 10px;
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.rank-left {
    display: flex;
    align-items: center;
    gap: 10px;
}

.rank-num {
    background-color: #1e293b;
    color: #38bdf8 !important;
    font-weight: 800;
    border-radius: 8px;
    padding: 4px 8px;
    min-width: 44px;
    text-align: center;
    font-size: 13px;
}

.title-text {
    font-size: 14px;
    font-weight: 700;
}

.badge-new {
    color: #f97316 !important;
    font-weight: 900;
    font-size: 13px;
}

.badge-up {
    color: #22c55e !important;
    font-weight: 900;
    font-size: 13px;
}

.badge-down {
    color: #ef4444 !important;
    font-weight: 900;
    font-size: 13px;
}

.small-text {
    color: #94a3b8 !important;
    font-size: 11px;
}

.section-card {
    background-color: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    margin-bottom: 6px;
}

hr {
    border-color: #334155;
}

/* 드롭다운 선택 박스 */
[data-baseweb="select"] * {
    color: #111827 !important;
}

/* 드롭다운 펼친 메뉴 */
[data-baseweb="popover"] * {
    color: #111827 !important;
    background-color: #ffffff !important;
}

/* 선택 라벨은 흰색 */
.stSelectbox label {
    color: #f8fafc !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎬 키노라이츠 랭킹 대시보드</h1>", unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">OTT/기간별 TOP100 랭킹 변화 모니터링</div>',
    unsafe_allow_html=True
)

file = Path("ranking_history.csv")

if not file.exists():
    st.error("ranking_history.csv 파일이 없습니다.")
    st.stop()

df = pd.read_csv(file)

if df.empty:
    st.error("수집된 데이터가 없습니다.")
    st.stop()

if "period" not in df.columns:
    df["period"] = "주간"

if "platform" not in df.columns:
    df["platform"] = "전체"

df["date"] = df["date"].astype(str)
df["period"] = df["period"].astype(str)
df["platform"] = df["platform"].astype(str)
df["title"] = df["title"].astype(str)
df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
df = df.dropna(subset=["rank", "title"])
df["rank"] = df["rank"].astype(int)

bad_titles = [
    "성별과 연령을 선택하고",
    "꼭 맞는 랭킹을 확인해 보세요",
    "트렌드 랭킹",
    "일간",
    "주간",
    "월간",
    "전체",
    "넷플릭스",
    "티빙",
    "쿠팡플레이",
    "웨이브",
    "디즈니+",
    "왓챠",
    "박스오피스"
]

df = df[~df["title"].isin(bad_titles)]

period_order = ["일간", "주간", "월간"]
platform_order = ["전체", "넷플릭스", "티빙", "쿠팡플레이", "웨이브", "디즈니+", "왓챠", "박스오피스"]

period_options = [
    x for x in period_order
    if x in df["period"].dropna().unique().tolist()
]

platform_options = [
    x for x in platform_order
    if x in df["platform"].dropna().unique().tolist()
]

if len(period_options) == 0:
    period_options = ["주간"]

if len(platform_options) == 0:
    platform_options = ["전체"]

default_period = period_options.index("주간") if "주간" in period_options else 0
default_platform = platform_options.index("전체") if "전체" in platform_options else 0

col_filter1, col_filter2 = st.columns(2)

with col_filter1:
    selected_period = st.selectbox(
        "기간 선택",
        period_options,
        index=default_period
    )

with col_filter2:
    selected_platform = st.selectbox(
        "OTT 선택",
        platform_options,
        index=default_platform
    )

filtered = df[
    (df["period"] == selected_period) &
    (df["platform"] == selected_platform)
].copy()

if filtered.empty:
    st.warning("선택한 조건의 데이터가 없습니다. Actions에서 Update Ranking을 다시 실행해보세요.")
    st.stop()

dates = sorted(filtered["date"].unique(), reverse=True)

demo_mode = False

if len(dates) < 2:
    demo_mode = True

    this_date = dates[0]
    this_week = filtered[filtered["date"] == this_date].copy()

    demo_date = (
        datetime.strptime(this_date, "%Y-%m-%d") - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    demo_titles = this_week["title"].tolist()
    demo_titles = demo_titles[8:45] + demo_titles[0:8] + demo_titles[45:90]
    demo_titles = demo_titles[:90]

    last_week = pd.DataFrame({
        "date": [demo_date] * len(demo_titles),
        "period": [selected_period] * len(demo_titles),
        "platform": [selected_platform] * len(demo_titles),
        "rank": range(1, len(demo_titles) + 1),
        "title": demo_titles
    })

    last_date = demo_date

else:
    this_date = dates[0]
    last_date = dates[1]

    this_week = filtered[filtered["date"] == this_date].copy()
    last_week = filtered[filtered["date"] == last_date].copy()

this_week = this_week.sort_values("rank").head(100)
last_week = last_week.sort_values("rank").head(100)

merged = this_week.merge(
    last_week[["title", "rank"]],
    on="title",
    how="left",
    suffixes=("_this", "_last")
)

merged["change"] = merged["rank_last"] - merged["rank_this"]

new_df = merged[merged["rank_last"].isna()].copy()

up_df = merged[merged["change"] > 0].copy()
up_df = up_df.sort_values("change", ascending=False)

down_df = merged[merged["change"] < 0].copy()
down_df = down_df.sort_values("change")

max_up_title = "-"
max_up_change = "-"

if len(up_df) > 0:
    max_up_title = up_df.iloc[0]["title"]
    max_up_change = f"▲{int(up_df.iloc[0]['change'])}"

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">TOP100 신규 진입</div>
        <div class="big-number">{len(new_df)}</div>
        <div class="card-sub">{selected_platform} / {selected_period}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">상승 작품</div>
        <div class="big-number">{len(up_df)}</div>
        <div class="card-sub">전주 대비 순위 상승</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">하락 작품</div>
        <div class="big-number">{len(down_df)}</div>
        <div class="card-sub">전주 대비 순위 하락</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="card-title">최대 상승</div>
        <div class="big-number">{max_up_change}</div>
        <div class="card-sub">{max_up_title}</div>
    </div>
    """, unsafe_allow_html=True)

if demo_mode:
    st.warning(
        "현재는 1회차 데이터만 있어서 테스트용 지난주 데이터를 자동 생성했습니다. "
        "다음 수집부터 실제 전주 대비 비교로 바뀝니다."
    )

st.markdown("---")

left, right = st.columns([1.25, 1])

with left:
    st.subheader(f"🏆 {selected_platform} {selected_period} TOP100 | {this_date}")

    for _, row in this_week.iterrows():
        title = row["title"]
        rank = int(row["rank"])

        matched = merged[merged["title"] == title]

        badge = '<span class="badge-new">NEW</span>'
        sub = "지난주 순위 없음"

        if not matched.empty:
            prev_rank = matched.iloc[0]["rank_last"]
            change = matched.iloc[0]["change"]

            if pd.notna(prev_rank):
                prev_rank = int(prev_rank)
                change = int(change)

                if change > 0:
                    badge = f'<span class="badge-up">▲{change}</span>'
                elif change < 0:
                    badge = f'<span class="badge-down">▼{abs(change)}</span>'
                else:
                    badge = '<span class="small-text">-</span>'

                sub = f"지난주 #{prev_rank}"

        st.markdown(f"""
        <div class="rank-card">
            <div class="rank-left">
                <div class="rank-num">#{rank}</div>
                <div>
                    <div class="title-text">{title}</div>
                    <div class="small-text">{sub}</div>
                </div>
            </div>
            <div>{badge}</div>
        </div>
        """, unsafe_allow_html=True)

with right:
    st.subheader("🔥 TOP100 신규 진입")

    if len(new_df) > 0:
        for _, row in new_df.sort_values("rank_this").head(30).iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="badge-new">NEW</span>
                &nbsp; #{int(row['rank_this'])} &nbsp;
                <b>{row['title']}</b>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("신규 진입 작품 없음")

    st.markdown("---")

    st.subheader("🚀 급상승 TOP20")

    if len(up_df) > 0:
        for _, row in up_df.head(20).iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="badge-up">▲{int(row['change'])}</span>
                &nbsp; <b>{row['title']}</b><br>
                <span class="small-text">
                    지난주 #{int(row['rank_last'])} → 이번주 #{int(row['rank_this'])}
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("급상승 작품 없음")

    st.markdown("---")

    st.subheader("📉 급하락 TOP20")

    if len(down_df) > 0:
        for _, row in down_df.head(20).iterrows():
            st.markdown(f"""
            <div class="section-card">
                <span class="badge-down">▼{abs(int(row['change']))}</span>
                &nbsp; <b>{row['title']}</b><br>
                <span class="small-text">
                    지난주 #{int(row['rank_last'])} → 이번주 #{int(row['rank_this'])}
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("급하락 작품 없음")

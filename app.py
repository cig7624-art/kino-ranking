import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="키노라이츠 랭킹", layout="wide")

st.title("키노라이츠 주간 랭킹 모니터링")

file = Path("ranking_history.csv")

if not file.exists():
    st.warning("아직 수집된 랭킹 데이터가 없습니다.")
    st.stop()

df = pd.read_csv(file)

dates = sorted(df["date"].unique(), reverse=True)

this_date = dates[0]
last_date = dates[1] if len(dates) > 1 else None

this_week = df[df["date"] == this_date].copy()

st.subheader(f"이번주 랭킹: {this_date}")
st.dataframe(this_week[["rank", "title"]], use_container_width=True)

if last_date:
    last_week = df[df["date"] == last_date].copy()

    merged = this_week.merge(
        last_week[["title", "rank"]],
        on="title",
        how="left",
        suffixes=("_this", "_last")
    )

    merged["change"] = merged["rank_last"] - merged["rank_this"]

    def status(row):
        if pd.isna(row["rank_last"]):
            return "NEW"
        elif row["change"] > 0:
            return f"▲{int(row['change'])}"
        elif row["change"] < 0:
            return f"▼{abs(int(row['change']))}"
        else:
            return "-"

    merged["변동"] = merged.apply(status, axis=1)

    st.subheader(f"지난주 대비 변동: {last_date} → {this_date}")
    st.dataframe(
        merged[["rank_this", "title", "rank_last", "변동"]]
        .rename(columns={
            "rank_this": "이번주 순위",
            "title": "작품명",
            "rank_last": "지난주 순위"
        }),
        use_container_width=True
    )

    out_titles = set(last_week["title"]) - set(this_week["title"])
    out_df = last_week[last_week["title"].isin(out_titles)]

    st.subheader("이탈 작품")
    st.dataframe(out_df[["rank", "title"]], use_container_width=True)

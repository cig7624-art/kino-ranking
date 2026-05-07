import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from pathlib import Path

URL = "https://m.kinolights.com/ranking/kino"

headers = {
    "User-Agent": "Mozilla/5.0"
}

res = requests.get(URL, headers=headers)

soup = BeautifulSoup(res.text, "lxml")

titles = []

for tag in soup.find_all("div"):
    cls = tag.get("class")

    if cls and "title" in cls:
        text = tag.get_text(strip=True)

        if text and text not in titles:
            titles.append(text)

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

    df = df.drop_duplicates(
        subset=["date", "title"]
    )

df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(df.tail())

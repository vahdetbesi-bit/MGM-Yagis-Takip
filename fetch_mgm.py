import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE = "https://www.mgm.gov.tr/sondurum/toplam-yagis.aspx"
OUT = Path("data.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_mm(text):
    text = text.replace("\xa0", " ").strip()
    text = text.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def fetch(day):
    params = {
        "gun": day.strftime("%d%m%y"),
        "t": "t",
    }

    response = requests.get(
        BASE,
        params=params,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    rows = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])

            if len(cells) < 2:
                continue

            values = [
                cell.get_text(" ", strip=True)
                for cell in cells
            ]

            name = values[0]
            rainfall_text = values[-1]

            if "," not in name:
                continue

            mm = parse_mm(rainfall_text)

            if mm is None:
                continue

            if mm < 0 or mm > 2000:
                continue

            parts = [x.strip() for x in name.split(",")]

            if len(parts) < 2:
                continue

            province = parts[0]
            station = parts[-1]

            rows.append({
                "date": day.isoformat(),
                "province": province,
                "station": station,
                "mm": round(mm, 1),
            })

    unique = {}

    for row in rows:
        key = (
            row["date"],
            row["province"],
            row["station"],
        )
        unique[key] = row

    return list(unique.values())


def main():
    if OUT.exists():
        try:
            old = json.loads(
                OUT.read_text(encoding="utf-8")
            )
        except Exception:
            old = []
    else:
        old = []

    database = {
        (
            item["date"],
            item["province"],
            item["station"],
        ): item
        for item in old
    }

    today = date.today()
    print("Bugün:", today)

    for n in range(4):
        day = today - timedelta(days=n)

        try:
            rows = fetch(day)
            print(f"{day}: {len(rows)} istasyon bulundu")

            for row in rows:
                key = (
                    row["date"],
                    row["province"],
                    row["station"],
                )
                database[key] = row

        except Exception as error:
            print(f"FAILED {day}: {error}")

        time.sleep(1)

    data = sorted(
        database.values(),
        key=lambda x: (
            x["date"],
            x["province"],
            x["station"],
        ),
    )

    OUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print("TOTAL", len(data))


if __name__ == "__main__":
    main()

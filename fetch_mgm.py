import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

BASE = "https://www.mgm.gov.tr/sondurum/toplam-yagis.aspx"
OUT = Path("data.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

def get_number(text):
    m = re.search(r"(-?\d+(?:[.,]\d+)?)", text.replace("\xa0", " "))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))

def fetch(day):
    # MGM'nin toplam yağış arşivinde kullanılan tarih biçimi: DDMMYY
    params = {
        "f": "",
        "gun": day.strftime("%d%m%y"),
        "ind": "0",
        "s": "za",
        "t": "t",
    }

    r = requests.get(
        BASE,
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "html.parser")
    rows = []

    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        texts = [c.get_text(" ", strip=True) for c in cells]
        name = texts[0]
        mm = get_number(texts[-1])

        # MGM satırları: "İl, İlçe, İstasyon | Yağış"
        parts = [p.strip() for p in name.split(",")]

        if len(parts) < 2:
            continue
        if mm is None or mm < 0 or mm > 2000:
            continue

        province = parts[0]
        station = parts[-1]

        # Başlık/menü gibi yanlış satırları ele
        if not province or not station:
            continue
        if "yağış" in name.lower() or "istasyon" in name.lower():
            continue

        rows.append({
            "date": day.isoformat(),
            "province": province,
            "station": station,
            "mm": round(mm, 1),
        })

    unique = {}
    for row in rows:
        key = (row["date"], row["province"], row["station"])
        unique[key] = row

    if not unique:
        raise RuntimeError(
            f"MGM'den 0 istasyon geldi. URL={r.url} HTTP={r.status_code}"
        )

    return list(unique.values())

def main():
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = []
    else:
        old = []

    db = {}
    for row in old:
        if all(k in row for k in ("date", "province", "station", "mm")):
            db[(row["date"], row["province"], row["station"])] = row

    today = date.today()
    print("Bugün:", today)

    success = 0

    for n in range(4):
        day = today - timedelta(days=n)

        try:
            rows = fetch(day)
            print(f"{day}: {len(rows)} istasyon bulundu")

            for row in rows:
                key = (row["date"], row["province"], row["station"])
                db[key] = row

            success += 1

        except Exception as e:
            print(f"FAILED {day}: {e}")

        time.sleep(1)

    if success == 0:
        raise RuntimeError("Hiçbir gün veri alınamadı; data.json değiştirilmedi.")

    data = sorted(
        db.values(),
        key=lambda x: (x["date"], x["province"], x["station"])
    )

    OUT.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )

    print("TOTAL", len(data))

if __name__ == "__main__":
    main()

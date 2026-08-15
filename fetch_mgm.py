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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def parse_mm(text):
    text = text.replace("\xa0", " ").strip()
    m = re.search(r"(-?\d+(?:[.,]\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def fetch(day):
    # MGM'nin arşiv sayfasında kullanılan parametre yapısı.
    params = {
        "f": "",
        "gun": day.strftime("%d%m%y"),
        "ind": "0",
        "s": "za",
        "t": "t",
    }

    url = BASE + "?" + urlencode(params)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    rows = []

    # Önce normal HTML tablo satırlarını oku.
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        values = [c.get_text(" ", strip=True) for c in cells]
        name = values[0]
        mm = parse_mm(values[-1])

        if mm is None or mm < 0 or mm > 2000:
            continue

        parts = [p.strip() for p in name.split(",")]

        # MGM istasyon satırları: İl, İlçe, İstasyon
        if len(parts) < 2:
            continue

        province = parts[0]
        station = parts[-1]

        if not province or not station:
            continue

        rows.append({
            "date": day.isoformat(),
            "province": province,
            "station": station,
            "mm": round(mm, 1),
        })

    # Bazı MGM sayfa sürümlerinde satırlar farklı HTML ile gelebilir.
    # Bu durumda doğrudan metin içinden "İl, İlçe, İstasyon | mm" biçimini dene.
    if not rows:
        text = soup.get_text("\n", strip=True)

        pattern = re.compile(
            r"(?m)^(.+?,.+?,.+?)\s*\|\s*(-?\d+(?:[.,]\d+)?)$"
        )

        for match in pattern.finditer(text):
            name = match.group(1).strip()
            mm = parse_mm(match.group(2))

            if mm is None or mm < 0 or mm > 2000:
                continue

            parts = [p.strip() for p in name.split(",")]
            if len(parts) < 2:
                continue

            rows.append({
                "date": day.isoformat(),
                "province": parts[0],
                "station": parts[-1],
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

    # 0 kayıt gerçek bir MGM sayfası yerine boş/beklenmeyen sayfa
    # gelmişse bunu sessizce başarılı kabul etme.
    if not unique:
        raise RuntimeError(
            f"MGM sayfasında istasyon bulunamadı. "
            f"HTTP={response.status_code}, bytes={len(response.content)}, URL={url}"
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

    database = {}

    for item in old:
        if all(k in item for k in ("date", "province", "station", "mm")):
            key = (
                item["date"],
                item["province"],
                item["station"],
            )
            database[key] = item

    today = date.today()
    print("Bugün:", today)

    successful_days = 0

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

            successful_days += 1

        except Exception as error:
            print(f"FAILED {day}: {error}")

        time.sleep(1)

    if successful_days == 0:
        raise RuntimeError("Hiçbir gün MGM'den veri alınamadı; data.json değiştirilmedi.")

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

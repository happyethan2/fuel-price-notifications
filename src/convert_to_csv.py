import json, csv
from datetime import datetime

with open("pricedata.json") as f:
    data = json.load(f)["Items"]

rows = []
for item in data:
    rows.append({
        "id": item["id"]["S"],
        "date": item["date"]["S"],
        "u91": item["u91"]["S"],
        "u95": item["u95"]["S"],
        "u98": item["u98"]["S"],
        "diesel": item["diesel"]["S"],
    })

# sort by date (ascending)
rows.sort(key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"))

with open("pricedata.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to pricedata.csv")

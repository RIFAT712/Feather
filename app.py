import json

with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

with open("names.txt", "w", encoding="utf-8") as f:
    for article in data["articles"]:
        f.write(article["name"] + "\n")

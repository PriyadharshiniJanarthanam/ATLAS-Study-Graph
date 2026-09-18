import os

data_path = "hackathon-data/data"

print("TESTING STARTED")

files = [
    "DM.csv",
    "AE.csv",
    "LB.csv",
    "VS.csv",
    "EX.csv",
    "CM.csv",
    "DS.csv",
    "MH.csv",
    "EG.csv"
]

for file in files:
    path = os.path.join(data_path, file)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            rows = sum(1 for line in f) - 1
        print(file, "OK -", rows, "records")
    else:
        print(file, "MISSING")

print("TESTING COMPLETED")
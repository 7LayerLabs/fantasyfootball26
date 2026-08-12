"""Fill team + 2026 bye week for all 230 players.

Teams: Sleeper NFL player database (current as of today).
Byes: 2026 schedule, verified against SI/NFL.com week groupings.
"""
import json, re

S = r"C:\Users\derek\AppData\Local\Temp\claude\C--Users-derek\51be7128-2b08-4038-953f-b27b86e2ee5a\scratchpad"

BYES = {"KC": 5, "CAR": 5, "MIA": 6, "CIN": 6, "DET": 6, "MIN": 6,
        "BUF": 7, "LAC": 7, "WAS": 7, "JAX": 7, "NYG": 8, "NO": 8, "SF": 8, "HOU": 8,
        "TEN": 9, "PIT": 9, "DEN": 10, "PHI": 10, "CHI": 10, "TB": 10,
        "NE": 11, "CLE": 11, "SEA": 11, "GB": 11, "ATL": 11, "LAR": 11,
        "IND": 13, "NYJ": 13, "LV": 13, "BAL": 13, "DAL": 14, "ARI": 14}

DST_ABBR = {"cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF",
            "panthers": "CAR", "bears": "CHI", "bengals": "CIN", "browns": "CLE",
            "cowboys": "DAL", "broncos": "DEN", "lions": "DET", "packers": "GB",
            "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC",
            "raiders": "LV", "chargers": "LAC", "rams": "LAR", "dolphins": "MIA",
            "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG",
            "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "49ers": "SF",
            "seahawks": "SEA", "buccaneers": "TB", "titans": "TEN", "commanders": "WAS"}

def norm(name):
    n = name.lower().strip()
    n = re.sub(r"[.'\-]", "", n)
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n)
    return re.sub(r"\s+", " ", n)

sp = json.load(open(f"{S}\\sleeper_players.json", encoding="utf-8"))
smap = {}
for v in sp.values():
    if v.get("position") in ("QB", "RB", "WR", "TE", "K") and v.get("team") and v.get("full_name"):
        key = (norm(v["full_name"]), v["position"])
        # prefer active players on name collisions
        if key not in smap or v.get("status") == "Active":
            smap[key] = v["team"]

data = json.load(open(f"{S}\\players.json", encoding="utf-8"))
unmatched, changed = [], []
for p in data["players"]:
    if p["pos"] == "DST":
        nick = norm(p["player"]).split()[-1]
        team = DST_ABBR.get(nick)
    else:
        team = smap.get((norm(p["player"]), p["pos"]))
    if not team:
        unmatched.append(f'{p["pos"]} {p["player"]} (kept: {p.get("team") or "none"})')
        team = p.get("team") or ""
    if p.get("team") and team and p["team"] != team:
        changed.append(f'{p["player"]}: {p["team"]} -> {team}')
    p["team"] = team
    p["bye"] = BYES.get(team, "")

json.dump(data, open(f"{S}\\players.json", "w", encoding="utf-8"), indent=1)
have = sum(1 for p in data["players"] if p["team"])
byes = sum(1 for p in data["players"] if p["bye"])
print(f"teams {have}/230, byes {byes}/230")
print("TEAM CHANGES vs old tags:", *changed, sep="\n  ") if changed else print("no team changes")
print("UNMATCHED:", *unmatched, sep="\n  ") if unmatched else print("all matched")

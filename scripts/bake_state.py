"""Bake Derek's live mock-draft state into draft-board.html."""
import json, re, sys
S = r"C:\Users\derek\AppData\Local\Temp\claude\C--Users-derek\51be7128-2b08-4038-953f-b27b86e2ee5a\scratchpad"

PICKS = []  # fresh board; add ("Player Name", 0=taken/1=mine) rows in draft order to bake a live draft in

def norm(n):
    n = n.lower().replace(".", "").replace("'", "")
    n = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", n.strip())
    return re.sub(r"[^a-z]", "", n)

data = json.load(open(S + r"\board_data.json", encoding="utf-8"))
lookup = {norm(p["name"]): p["overall"] for p in data}
assert len(lookup) == len(data), "normalization collision in player pool"

# merge ESPN overall ranks (Yates top 160, scraped 8/12) so mock-draft bots can draft off ESPN's board
try:
    espn = json.load(open(S + r"\espn_parsed.json", encoding="utf-8"))
    emap = {norm(name): rank for rank, name, *_ in espn["yates"]}
    emap[norm("Bijan Robinson")] = 1  # rank 1 glued to intro text in the scrape
    n_esp = 0
    for p in data:
        r = emap.get(norm(p["name"]))
        p["espn"] = r
        n_esp += r is not None
    print(f"espn ranks merged: {n_esp}/{len(data)}")
except FileNotFoundError:
    for p in data:
        p.setdefault("espn", None)
    print("espn_parsed.json not found; espn ranks skipped")

status, hist, misses = {}, [], []
for name, mine in PICKS:
    o = lookup.get(norm(name))
    if o is None:
        misses.append(name); continue
    status[str(o)] = "M" if mine else "T"
    hist.append(o)
if misses:
    print("UNMATCHED:", misses); sys.exit(1)

init = {"status": status, "hist": hist, "teams": 10, "slot": 9}
tpl = open(S + r"\board_template.html", encoding="utf-8").read()
assert "__DATA__" in tpl and "__INIT__" in tpl
out = tpl.replace("__DATA__", json.dumps(data)).replace("__INIT__", json.dumps(init))
dest = r"C:\Users\derek\Downloads\Documents\draft-board.html"
open(dest, "w", encoding="utf-8").write(out)
mine_names = [n for n, m in PICKS if m]
print(f"BAKED {len(hist)} picks ({len(mine_names)} mine: {', '.join(mine_names)}) -> {dest}")

"""Rebuild board_data.json directly from players.json (for when Excel isn't available)."""
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PLAYERS_JSON = SCRIPT_DIR / "players.json"
BOARD_DATA_JSON = SCRIPT_DIR / "board_data.json"

def tier(r):
    for t, lo in [("ELITE", 95), ("TIER 1", 90), ("TIER 2", 85), ("TIER 3", 80),
                  ("TIER 4", 75), ("TIER 5", 70), ("TIER 6", 65)]:
        if r >= lo: return t
    return "TIER 7"

# Load players.json
with open(PLAYERS_JSON, encoding="utf-8") as f:
    data = json.load(f)

players = data["players"]

# First pass: group by position and find positional baselines
pos_groups = {"QB": [], "RB": [], "WR": [], "TE": [], "K": [], "DST": []}
for p in players:
    pos = p["pos"]
    if pos in pos_groups:
        pos_groups[pos].append(p)

# Calculate position-specific replacement levels
# For skill positions: use a standard replacement level
# For K and DST: use a replacement level very close to the top player to minimize VORP
replacement_levels = {
    "QB": 70,
    "RB": 70,
    "WR": 70,
    "TE": 70,
    "K": 92,   # Close to top K rating (94) so VORP is small
    "DST": 91  # Close to top DST rating (93) so VORP is small
}

# Build output in the same format as extract_board.py
out = []
for i, p in enumerate(players):
    rating = round(p["base"], 1)
    pos = p["pos"]
    
    # Position-aware VORP calculation
    replacement = replacement_levels.get(pos, 70)
    vorp_proxy = max(0, (rating - replacement) * 2)
    
    # For skill positions, score is rating-based
    # For K/DST, score is also rating-based but VORP is tiny
    score_proxy = rating
    
    out.append({
        "pos": pos,
        "name": p["player"],
        "team": p.get("team", ""),
        "bye": p.get("bye", 0),
        "rating": rating,
        "tier": tier(rating),
        "posRank": 0,  # Will be calculated below
        "pts": 0,  # Approximation not available
        "vorp": round(vorp_proxy, 1),
        "score": round(score_proxy, 1),
        "overall": i + 1,  # Temp, will be recalculated
        "adp": round(p["adp"], 1),
        "edge": 0,  # Will be calculated after sorting
        "conf": p.get("confidence", "B"),
        "floor": round(max(40, rating - 6), 1),
        "ceil": round(min(100, rating + 6), 1),
        "rookie": p.get("model_path") == "ROOKIE ENGINE",
        "exp": p.get("expectation", ""),
        "risk": p.get("risk", ""),
        # Add opportunity fields
        "snap_share": p.get("snap_share", 0),
        "route_share": p.get("route_share", 0),
        "carry_share": p.get("carry_share", 0),
        "target_share": p.get("target_share", 0),
        "rz_share": p.get("rz_share", 0),
        "expected_ppg": p.get("expected_ppg", 0),
        "actual_ppg": p.get("actual_ppg", 0),
        "games_played": p.get("games_played", 0),
        "sample_note": p.get("sample_note", ""),
        "qb_situation": p.get("qb_situation", ""),
        "role": p.get("role", ""),
        "opp_score": p.get("opp_score", 0),
        # Add counting stats
        "rush_att": p.get("rush_att", 0),
        "rush_yds": p.get("rush_yds", 0),
        "rush_td": p.get("rush_td", 0),
        "rec": p.get("rec", 0),
        "rec_yds": p.get("rec_yds", 0),
        "rec_td": p.get("rec_td", 0),
        "pass_yds": p.get("pass_yds", 0),
        "pass_td": p.get("pass_td", 0),
        # Add detail fields
        "team_qb": p.get("team_qb", ""),
        "handcuff": p.get("handcuff", ""),
        "age": p.get("age"),
        "stats_season": p.get("stats_season")
    })

# Separate skill positions from K/DST
skill_players = [p for p in out if p["pos"] in ["QB", "RB", "WR", "TE"]]
kickers = [p for p in out if p["pos"] == "K"]
defenses = [p for p in out if p["pos"] == "DST"]

# Sort each group by score (rating)
skill_players.sort(key=lambda p: -p["score"])
kickers.sort(key=lambda p: -p["score"])
defenses.sort(key=lambda p: -p["score"])

# Concatenate: skill positions first, then kickers, then defenses
out = skill_players + kickers + defenses

# Assign overall ranks and position ranks
pos_counts = {}
for i, p in enumerate(out):
    p["overall"] = i + 1
    pos = p["pos"]
    pos_counts[pos] = pos_counts.get(pos, 0) + 1
    p["posRank"] = pos_counts[pos]
    # Calculate edge (ADP - overall rank)
    p["edge"] = round(p["adp"] - p["overall"], 1)

with open(BOARD_DATA_JSON, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)

print(f"OK {len(out)} players; {out[0]['name']} -> {out[-1]['name']}")
print(f"Added opportunity data for {len([p for p in out if p['games_played'] > 0])} players with NFL data")

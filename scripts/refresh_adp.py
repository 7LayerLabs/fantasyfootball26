#!/usr/bin/env python3
"""
Refresh Market ADP from manual JSON file.

Updates only the 'adp' field in players.json, preserving all base ratings and opinions.

Usage:
    python3 refresh_adp.py

To use:
1. Create scripts/manual_adp.json with current ADP values (see example below)
2. Run this script to update players.json
3. Rebuild the board (see WORKFLOW.md)

ADP Data Sources:
- Sleeper: https://sleeper.com/draft/nfl/rankings (view network tab for API)
- FantasyPros: https://www.fantasypros.com/nfl/adp/ppr-overall.php
- Underdog Fantasy: https://underdogfantasy.com/pick-em/higher-lower
- Your league platform's consensus ADP

Sleeper API Note:
The Sleeper API for 2026 ADP is not yet publicly documented. When the season
is active, ADP data may be available via their trending/projections endpoints.
For now, manual JSON is the recommended path.
"""
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PLAYERS_JSON = SCRIPT_DIR / "players.json"
MANUAL_ADP_JSON = SCRIPT_DIR / "manual_adp.json"

EXAMPLE_MANUAL_ADP = {
    "Puka Nacua": 2.8,
    "Bijan Robinson": 1.9,
    "Ja'Marr Chase": 3.1,
    "Christian McCaffrey": 4.2,
    "Jaxon Smith-Njigba": 5.5,
}

def normalize_name(name):
    """Normalize player name for matching (lowercase, no punctuation, no suffixes)."""
    name = name.lower().replace(".", "").replace("'", "").replace("-", " ")
    name = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", name.strip())
    return re.sub(r"[^a-z\s]", "", name).strip()

def load_manual_adp():
    """
    Load ADP from manual_adp.json.
    
    Format: {"Player Name": adp_value, ...}
    
    Returns dict: {normalized_name: adp_value}
    """
    if not MANUAL_ADP_JSON.exists():
        return None
    
    print(f"Loading manual ADP from {MANUAL_ADP_JSON.name}...")
    try:
        with open(MANUAL_ADP_JSON, encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            print(f"Error: {MANUAL_ADP_JSON.name} must be a dict of {{'Player Name': adp_value}}")
            return None
        
        # Normalize keys
        result = {}
        for name, adp in data.items():
            if not isinstance(adp, (int, float)):
                print(f"Warning: Skipping {name} - ADP must be a number, got {type(adp).__name__}")
                continue
            result[normalize_name(name)] = float(adp)
        
        print(f"  Loaded {len(result)} players from manual ADP file")
        return result
    
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {MANUAL_ADP_JSON.name}: {e}")
        return None
    except Exception as e:
        print(f"Error loading {MANUAL_ADP_JSON.name}: {e}")
        return None

def update_adp_values(adp_source):
    """
    Update ADP values in players.json.
    
    Args:
        adp_source: dict of {normalized_name: adp_value}
    """
    print(f"\nLoading {PLAYERS_JSON}...")
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    
    players = data["players"]
    
    # Build lookup
    name_to_player = {}
    for p in players:
        norm_name = normalize_name(p["player"])
        name_to_player[norm_name] = p
    
    # Update ADP values
    updated = 0
    unchanged = 0
    not_found = []
    
    for norm_name, new_adp in adp_source.items():
        if norm_name in name_to_player:
            player = name_to_player[norm_name]
            old_adp = player["adp"]
            
            # Update if different (threshold: 0.1 to avoid float precision noise)
            if abs(old_adp - new_adp) > 0.1:
                player["adp"] = round(new_adp, 1)
                print(f"  Updated {player['player']:25s}: {old_adp:6.1f} → {new_adp:6.1f}")
                updated += 1
            else:
                unchanged += 1
        else:
            not_found.append(norm_name)
    
    if updated > 0:
        print(f"\nWriting updated players.json ({updated} changes)...")
        with open(PLAYERS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print("Done!")
    else:
        print("\nNo ADP changes needed.")
    
    print(f"\nSummary:")
    print(f"  Updated: {updated}")
    print(f"  Unchanged: {unchanged}")
    print(f"  Not found in our pool: {len(not_found)}")
    
    if not_found and len(not_found) <= 20:
        print(f"\n  Missing from our 230-player pool:")
        for name in sorted(not_found)[:20]:
            print(f"    - {name}")

def create_example_file():
    """Create an example manual_adp.json file."""
    print(f"\nCreating example {MANUAL_ADP_JSON.name}...")
    
    example_content = {
        "_comment": "ADP values for 2026 PPR drafts. Update with current market data from Sleeper, FantasyPros, or Underdog.",
        **EXAMPLE_MANUAL_ADP
    }
    
    with open(MANUAL_ADP_JSON, "w", encoding="utf-8") as f:
        json.dump(example_content, f, indent=2, ensure_ascii=False)
    
    print(f"Created {MANUAL_ADP_JSON}")
    print("\nNext steps:")
    print("  1. Edit scripts/manual_adp.json with current ADP values from your source")
    print("  2. Run this script again: python3 scripts/refresh_adp.py")

def main():
    """Main ADP refresh workflow."""
    print("=" * 70)
    print("ADP Refresh Tool")
    print("=" * 70)
    print()
    
    adp_data = load_manual_adp()
    
    if adp_data:
        update_adp_values(adp_data)
    else:
        print("=" * 70)
        print("No ADP source available")
        print("=" * 70)
        print()
        
        if MANUAL_ADP_JSON.exists():
            print(f"Error: {MANUAL_ADP_JSON} exists but could not be loaded.")
            print("Check the file format (JSON dict of player name: ADP value)")
        else:
            print(f"{MANUAL_ADP_JSON.name} not found.")
            print()
            
            response = input("Create an example manual_adp.json file? (y/n): ").strip().lower()
            if response == "y":
                create_example_file()
            else:
                print("\nManual setup:")
                print(f"  1. Create {MANUAL_ADP_JSON}")
                print("  2. Format: {")
                print('       "Puka Nacua": 2.8,')
                print('       "Bijan Robinson": 1.9,')
                print('       "Ja\'Marr Chase": 3.1,')
                print("       ...")
                print("     }")
                print("  3. Get ADP from Sleeper, FantasyPros, or Underdog")
                print("  4. Run this script again")

if __name__ == "__main__":
    main()

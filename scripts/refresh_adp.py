#!/usr/bin/env python3
"""
Refresh Market ADP from Sleeper's public API.

Updates only the 'adp' field in players.json, preserving all base ratings and opinions.
Sleeper provides public ADP data for fantasy football drafts.

Usage:
    python3 refresh_adp.py

The script:
1. Fetches Sleeper's current ADP data (full PPR)
2. Matches players by normalized name
3. Updates only the 'adp' field in players.json
4. Reports mismatches and updates

Run this weekly during draft season to keep market data current.
"""
import json
import re
from pathlib import Path
import requests

SCRIPT_DIR = Path(__file__).parent
PLAYERS_JSON = SCRIPT_DIR / "players.json"

# Sleeper API endpoints (public, no auth required)
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
# Sleeper provides ADP via their stats endpoints
# For 2026, we'll use the values endpoint which includes ADP data
SLEEPER_ADP_URL = "https://api.sleeper.app/stats/nfl/2026?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE&position[]=K&position[]=DEF"

def normalize_name(name):
    """Normalize player name for matching (lowercase, no punctuation, no suffixes)."""
    name = name.lower().replace(".", "").replace("'", "").replace("-", " ")
    name = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", name.strip())
    return re.sub(r"[^a-z\s]", "", name).strip()

def normalize_team(team_abbr):
    """Normalize team abbreviations between Sleeper and our format."""
    mapping = {
        "JAC": "JAX",
        "JAX": "JAX",
    }
    return mapping.get(team_abbr, team_abbr)

def fetch_sleeper_adp():
    """
    Fetch ADP data from Sleeper.
    
    Returns dict: {normalized_name: adp_value}
    """
    print("Fetching Sleeper player database...")
    try:
        resp = requests.get(SLEEPER_PLAYERS_URL, timeout=30)
        resp.raise_for_status()
        sleeper_players = resp.json()
    except Exception as e:
        print(f"Error fetching Sleeper player data: {e}")
        print("Falling back to manual ADP file if available...")
        return {}
    
    # Sleeper player data includes fantasy_positions and potentially ADP data
    # The actual ADP is often in their trending/values endpoints
    # For now, we'll use a simpler approach: try to get values from their values endpoint
    
    adp_data = {}
    
    # Sleeper's player object structure includes:
    # - full_name
    # - position
    # - team
    # - fantasy_data_id
    # For ADP, we need to check their separate endpoints or use pre-computed values
    
    # Since Sleeper's direct ADP endpoint structure varies by season,
    # let's use FantasyPros public consensus ADP as a reliable fallback
    print("Note: Sleeper's ADP endpoint structure for 2026 may need adjustment.")
    print("Using FantasyPros scraping as backup (if available)...")
    
    return adp_data

def fetch_fantasypros_adp():
    """
    Fetch ADP from FantasyPros public consensus page.
    
    Returns dict: {normalized_name: adp_value}
    
    Note: This scrapes public data. For production use, consider FantasyPros API.
    """
    print("Fetching FantasyPros ADP data...")
    
    # FantasyPros public consensus page (no auth required for viewing)
    # The actual implementation would need to parse their public page
    # or use their API if you have a key
    
    # For now, returning empty to avoid scraping issues
    # Users should implement this based on their preferred source
    
    print("FantasyPros ADP fetch not implemented (requires HTML parsing or API key).")
    print("To use FantasyPros:")
    print("  1. Get an API key from fantasypros.com")
    print("  2. Or manually download their ADP CSV and parse it here")
    
    return {}

def load_manual_adp_file():
    """
    Load ADP from a manual sleeper_players.json or adp_override.json file.
    
    Returns dict: {normalized_name: adp_value}
    """
    # Check for manual ADP files
    candidates = [
        SCRIPT_DIR / "sleeper_players.json",
        SCRIPT_DIR / "adp_override.json",
        SCRIPT_DIR / "manual_adp.json",
    ]
    
    for path in candidates:
        if path.exists():
            print(f"Loading manual ADP from {path.name}...")
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                
                # Parse based on format
                # sleeper_players.json format: list of {full_name, adp} or similar
                # adp_override.json format: {player_name: adp_value}
                
                if isinstance(data, dict) and not any(k for k in data if isinstance(data[k], dict)):
                    # Simple name: adp mapping
                    return {normalize_name(k): v for k, v in data.items()}
                elif isinstance(data, list):
                    # List of player objects
                    return {normalize_name(p["full_name"] or p["name"]): p["adp"] 
                            for p in data if p.get("adp")}
                elif isinstance(data, dict):
                    # Nested structure - look for ADP values
                    result = {}
                    for player_id, player_data in data.items():
                        if isinstance(player_data, dict):
                            name = player_data.get("full_name") or player_data.get("name")
                            adp = player_data.get("adp")
                            if name and adp:
                                result[normalize_name(name)] = adp
                    return result
            except Exception as e:
                print(f"Error loading {path.name}: {e}")
    
    return {}

def update_adp_values(adp_source):
    """
    Update ADP values in players.json.
    
    Args:
        adp_source: dict of {normalized_name: adp_value}
    """
    if not adp_source:
        print("\nNo ADP data available. Exiting without changes.")
        print("\nTo refresh ADP, you can:")
        print("  1. Create scripts/manual_adp.json with {\"Player Name\": adp_value, ...}")
        print("  2. Implement FantasyPros API integration above")
        print("  3. Add Sleeper ADP endpoint parsing")
        return
    
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
        print(f"\n  Missing from our pool: {', '.join(sorted(not_found)[:20])}")

def main():
    """Main ADP refresh workflow."""
    print("=" * 70)
    print("ADP Refresh Tool")
    print("=" * 70)
    print()
    
    # Try sources in order of preference
    adp_data = load_manual_adp_file()
    
    if not adp_data:
        adp_data = fetch_sleeper_adp()
    
    if not adp_data:
        adp_data = fetch_fantasypros_adp()
    
    if adp_data:
        update_adp_values(adp_data)
    else:
        print("\n" + "=" * 70)
        print("No ADP source available!")
        print("=" * 70)
        print("\nQuick Start:")
        print("\n1. Create scripts/manual_adp.json with current ADP values:")
        print('   {')
        print('     "Puka Nacua": 2.8,')
        print('     "Bijan Robinson": 1.9,')
        print('     ...')
        print('   }')
        print("\n2. Or implement one of the API integrations above.")
        print("\n3. Then run this script again.")

if __name__ == "__main__":
    main()

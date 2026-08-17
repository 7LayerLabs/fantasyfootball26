"""Add opportunity analytics layers to players.json.

Layer 1: Opportunity columns (snap share, route/carry share, target share, RZ share, xFP)
Layer 2: Situation fields (QB situation, role, injury/sample notes)
Layer 3: Opportunity-based lens data for sorting
"""
import json
import warnings
from pathlib import Path
from collections import defaultdict

warnings.filterwarnings("ignore")

try:
    import nfl_data_py as nfl
    import pandas as pd
    NFL_DATA_AVAILABLE = True
except ImportError:
    NFL_DATA_AVAILABLE = False
    print("WARNING: nfl_data_py not available, using placeholder data")

SCRIPT_DIR = Path(__file__).parent
PLAYERS_JSON = SCRIPT_DIR / "players.json"


def load_nfl_data():
    """Load 2025 regular season NFL data."""
    if not NFL_DATA_AVAILABLE:
        return None, None, None, None, None
    
    # Try 2025 first, fall back to 2024 if not available
    for year in [2025, 2024]:
        try:
            print(f"Loading {year} NFL regular season data...")
            
            # Load play-by-play data
            pbp = nfl.import_pbp_data([year], downcast=False)
            pbp_reg = pbp[pbp['season_type'] == 'REG'].copy()
            
            # Load weekly data for stats
            weekly = nfl.import_weekly_data([year], downcast=False)
            weekly_reg = weekly[weekly['season_type'] == 'REG'].copy()
            
            # Load snap counts
            snaps = nfl.import_snap_counts([year])
            snaps_reg = snaps[snaps['game_type'] == 'REG'].copy()
            
            # Load rosters for age/team mapping
            rosters = nfl.import_seasonal_rosters([year])
            
            print(f"Successfully loaded {year} data")
            return pbp_reg, weekly_reg, snaps_reg, rosters, year
        except Exception as e:
            print(f"Failed to load {year} data: {e}")
            if year == 2024:
                print("No NFL data available, using placeholder")
                return None, None, None, None, None
            continue
    
    return None, None, None, None, None


def calculate_qb_grades(pbp_reg):
    """Calculate QB situation grades based on 2025 performance."""
    if pbp_reg is None:
        return {}
    
    qb_stats = pbp_reg[pbp_reg['qb_dropback'] == 1].groupby(['posteam', 'passer_player_name']).agg({
        'pass_attempt': 'sum',
        'complete_pass': 'sum',
        'pass_touchdown': 'sum',
        'interception': 'sum',
        'epa': 'mean',
        'cpoe': 'mean'
    }).reset_index()
    
    # Filter to primary QBs (100+ attempts)
    qb_stats = qb_stats[qb_stats['pass_attempt'] >= 100].copy()
    
    # Calculate composite score
    qb_stats['score'] = (qb_stats['epa'] * 50 + qb_stats['cpoe'] * 20)
    
    # Map to team and grade
    team_qb_grades = {}
    for _, row in qb_stats.iterrows():
        team = row['posteam']
        score = row['score']
        
        if score >= 3.0:
            grade = "elite"
        elif score >= 1.0:
            grade = "average"
        elif score >= -1.0:
            grade = "weakness"
        else:
            grade = "weakness"
        
        team_qb_grades[team] = grade
    
    return team_qb_grades


def normalize_name(name):
    """Normalize player name for matching."""
    # Remove Jr., Sr., II, III, IV, V suffixes
    name = name.replace(' Jr.', '').replace(' Sr.', '')
    name = name.replace(' II', '').replace(' III', '').replace(' IV', '').replace(' V', '')
    return name.strip()


def find_best_name_match(player_name, nfl_players):
    """Find best matching NFL player name."""
    normalized = normalize_name(player_name)
    
    # Try exact match first
    if normalized in nfl_players:
        return nfl_players[normalized]
    
    # Try last name match
    last_name = normalized.split()[-1]
    matches = [p for p in nfl_players if p.split()[-1] == last_name]
    if len(matches) == 1:
        return nfl_players[matches[0]]
    
    return None


def calculate_opportunity_metrics(weekly_reg, snaps_reg, pbp_reg):
    """Calculate per-player opportunity metrics and counting stats."""
    if weekly_reg is None or pbp_reg is None:
        return {}
    
    metrics = {}
    
    # Build a normalized name lookup for NFL players
    nfl_player_lookup = {}
    for _, row in weekly_reg[['player_display_name']].drop_duplicates().iterrows():
        nfl_name = row['player_display_name']
        normalized = normalize_name(nfl_name)
        nfl_player_lookup[normalized] = nfl_name
    
    # Aggregate weekly data by player (use display_name for matching)
    player_weekly = weekly_reg.groupby(['player_display_name', 'player_id', 'position', 'recent_team']).agg({
        'carries': 'sum',
        'rushing_yards': 'sum',
        'rushing_tds': 'sum',
        'targets': 'sum',
        'receptions': 'sum',
        'receiving_yards': 'sum',
        'receiving_tds': 'sum',
        'passing_yards': 'sum',
        'passing_tds': 'sum',
        'fantasy_points_ppr': 'sum',
        'week': 'count'
    }).reset_index()
    player_weekly.rename(columns={'week': 'games'}, inplace=True)
    
    # Aggregate snap counts by player
    if snaps_reg is not None:
        player_snaps = snaps_reg.groupby(['player', 'position', 'team']).agg({
            'offense_snaps': 'sum',
            'offense_pct': 'mean'
        }).reset_index()
    else:
        player_snaps = pd.DataFrame()
    
    # Calculate team totals for share metrics
    team_totals = weekly_reg.groupby('recent_team').agg({
        'carries': 'sum',
        'targets': 'sum'
    }).reset_index()
    team_totals.columns = ['team', 'team_carries', 'team_targets']
    
    # Red zone stats from play-by-play
    rz_pbp = pbp_reg[pbp_reg['yardline_100'] <= 20].copy()
    
    rz_carries = rz_pbp[rz_pbp['rusher_player_name'].notna()].groupby('rusher_player_name')['rush_attempt'].sum()
    rz_targets = rz_pbp[rz_pbp['receiver_player_name'].notna()].groupby('receiver_player_name')['pass_attempt'].sum()
    
    # Build metrics dict (keyed by display_name)
    for _, row in player_weekly.iterrows():
        player = row['player_display_name']
        team = row['recent_team']
        pos = row['position']
        
        # Get team totals
        team_data = team_totals[team_totals['team'] == team]
        if team_data.empty:
            continue
        
        team_carries = team_data['team_carries'].iloc[0]
        team_targets = team_data['team_targets'].iloc[0]
        
        # Get snap data (use player name from weekly)
        snap_share = 0
        if not player_snaps.empty:
            # Try to match by last name
            last_name = player.split()[-1]
            snap_data = player_snaps[player_snaps['player'].str.contains(last_name, case=False, na=False)]
            if not snap_data.empty:
                snap_share = round(snap_data['offense_pct'].iloc[0] * 100, 1)
        
        # Calculate shares
        if pos == 'RB':
            carry_share = round(100 * row['carries'] / team_carries, 1) if team_carries > 0 else 0
            # Route share approximation for RBs: targets / team_targets * 0.8
            route_share = round(100 * row['targets'] / team_targets * 0.8, 1) if team_targets > 0 and row['targets'] > 0 else 0
        else:
            carry_share = 0
            # Route share approximation for WR/TE: targets / team_targets
            route_share = round(100 * row['targets'] / team_targets, 1) if team_targets > 0 and row['targets'] > 0 else 0
        
        target_share = round(100 * row['targets'] / team_targets, 1) if team_targets > 0 and row['targets'] > 0 else 0
        
        # Red zone share (total touches in RZ) - use abbreviated name
        player_abbrev = player.split()[0][0] + '.' + player.split()[-1]
        rz_share = 0
        if player_abbrev in rz_carries.index:
            rz_share += rz_carries[player_abbrev]
        if player_abbrev in rz_targets.index:
            rz_share += rz_targets[player_abbrev]
        rz_share = round(rz_share, 0)
        
        # Expected fantasy points (simple volume-based proxy)
        games = row['games'] if row['games'] > 0 else 1
        actual_ppg = row['fantasy_points_ppr'] / games
        
        # xFP proxy: based on usage
        if pos == 'RB':
            expected_ppg = (row['carries'] / games) * 0.1 + (row['targets'] / games) * 0.5
        elif pos in ['WR', 'TE']:
            expected_ppg = (row['targets'] / games) * 0.5
        else:
            expected_ppg = actual_ppg
        
        # Store both normalized and display name
        metrics[player] = {
            '_display_name': player,
            'snap_share': snap_share,
            'route_share': route_share if pos in ['WR', 'TE', 'RB'] else 0,
            'carry_share': carry_share if pos == 'RB' else 0,
            'target_share': target_share if pos in ['WR', 'TE', 'RB'] else 0,
            'rz_share': rz_share,
            'expected_ppg': round(expected_ppg, 1),
            'actual_ppg': round(actual_ppg, 1),
            'games_played': int(row['games']),
            # Counting stats
            'rush_att': int(row['carries']) if pos in ['RB', 'QB'] else 0,
            'rush_yds': int(row['rushing_yards']) if pos in ['RB', 'QB'] else 0,
            'rush_td': int(row['rushing_tds']) if pos in ['RB', 'QB'] else 0,
            'rec': int(row['receptions']) if pos in ['RB', 'WR', 'TE'] else 0,
            'rec_yds': int(row['receiving_yards']) if pos in ['RB', 'WR', 'TE'] else 0,
            'rec_td': int(row['receiving_tds']) if pos in ['RB', 'WR', 'TE'] else 0,
            'pass_yds': int(row['passing_yards']) if pos == 'QB' else 0,
            'pass_td': int(row['passing_tds']) if pos == 'QB' else 0
        }
    
    return metrics, nfl_player_lookup


def determine_role(player, pos, metrics):
    """Determine player role based on usage."""
    if pos not in ['RB', 'WR', 'TE']:
        return ""
    
    if player not in metrics:
        return "unclear"
    
    m = metrics[player]
    snap = m['snap_share']
    
    if pos == 'RB':
        carry = m['carry_share']
        if carry >= 50 and snap >= 50:
            return "feature"
        elif carry >= 25:
            return "committee"
        else:
            return "handcuff"
    else:
        target = m['target_share']
        if target >= 25 and snap >= 70:
            return "feature"
        elif target >= 15:
            return "committee"
        else:
            return "unclear"


def generate_suggested_adjustments(players, metrics, qb_grades):
    """Generate rating adjustment suggestions based on opportunity data."""
    suggestions = []
    
    for p in players:
        if p['pos'] in ['K', 'DST']:
            continue
        
        player = p['player']
        pos = p['pos']
        current_adp = p['adp']
        current_base = p['base']
        team = p.get('team', '')
        
        # Get metrics
        m = metrics.get(player, {})
        if not m:
            continue
        
        # Skip rookies (no NFL sample)
        if m.get('games_played', 0) < 8:
            continue
        
        # Check for opportunity/ADP mismatch
        snap = m.get('snap_share', 0)
        target = m.get('target_share', 0)
        carry = m.get('carry_share', 0)
        
        # High usage, late ADP = undervalued
        if pos == 'RB' and carry >= 40 and snap >= 50 and current_adp > 80:
            adj = 5
            reason = f"Feature back usage ({carry}% carry, {snap}% snap) vs ADP {current_adp}"
            suggestions.append((player, adj, reason, abs(current_adp - 60)))
        
        elif pos in ['WR', 'TE'] and target >= 22 and snap >= 65 and current_adp > 100:
            adj = 4
            qb_situation = qb_grades.get(team, "unknown")
            if qb_situation == "weakness":
                reason = f"High target share ({target}%) but weak QB situation vs ADP {current_adp}"
                adj = 2
            else:
                reason = f"Feature target share ({target}%, {snap}% snap) vs ADP {current_adp}"
            suggestions.append((player, adj, reason, abs(current_adp - 80)))
        
        # Early ADP but limited usage = overvalued
        elif pos == 'RB' and carry < 25 and current_adp < 70 and snap < 50:
            adj = -4
            reason = f"Committee role ({carry}% carry, {snap}% snap) vs ADP {current_adp}"
            suggestions.append((player, adj, reason, abs(70 - current_adp)))
        
        elif pos == 'WR' and target < 18 and current_adp < 60:
            qb_situation = qb_grades.get(team, "unknown")
            adj = -3
            reason = f"Limited target share ({target}%) vs WR1/2 ADP {current_adp}"
            if qb_situation == "weakness":
                adj = -4
                reason = f"Limited targets ({target}%) + weak QB vs early ADP {current_adp}"
            suggestions.append((player, adj, reason, abs(60 - current_adp)))
    
    # Sort by strength (absolute adjustment value + ADP gap)
    suggestions.sort(key=lambda x: x[3], reverse=True)
    
    return suggestions[:15]


def get_player_age(rosters, player_name):
    """Get player age from rosters if available."""
    if rosters is None or rosters.empty:
        return None
    
    # Try exact match first
    player_data = rosters[rosters['player_name'] == player_name]
    if player_data.empty:
        # Try partial match on last name
        last_name = player_name.split()[-1]
        player_data = rosters[rosters['player_name'].str.contains(last_name, case=False, na=False)]
    
    if not player_data.empty and 'age' in rosters.columns:
        age_val = player_data['age'].iloc[0]
        if pd.notna(age_val):
            return int(age_val)
    return None


def compute_team_qb(players):
    """Find the starting QB for each team (highest base QB on that team)."""
    team_qbs = {}
    for p in players:
        if p['pos'] == 'QB' and p.get('team'):
            team = p['team']
            if team not in team_qbs or p['base'] > team_qbs[team]['base']:
                team_qbs[team] = {'name': p['player'], 'base': p['base']}
    
    return {team: qb['name'] for team, qb in team_qbs.items()}


def compute_handcuffs_and_committee(players, metrics):
    """Find handcuffs and committee mates for RBs."""
    handcuffs = {}
    
    for p in players:
        if p['pos'] == 'RB' and p.get('team'):
            team = p['team']
            player_name = p['player']
            
            # Get all RBs on same team
            team_rbs = [
                {
                    'name': pl['player'],
                    'carry_share': metrics.get(pl['player'], {}).get('carry_share', 0),
                    'base': pl['base']
                }
                for pl in players
                if pl['pos'] == 'RB' and pl.get('team') == team and pl['player'] != player_name
            ]
            
            # Sort by carry_share desc, then base desc
            team_rbs.sort(key=lambda x: (-x['carry_share'], -x['base']))
            
            handcuffs[player_name] = [rb['name'] for rb in team_rbs]
    
    return handcuffs


def main():
    print("Loading players.json...")
    with open(PLAYERS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    
    players = data['players']
    
    # Load NFL data
    pbp_reg, weekly_reg, snaps_reg, rosters, season_year = load_nfl_data()
    
    # Calculate metrics
    if pbp_reg is not None:
        qb_grades = calculate_qb_grades(pbp_reg)
        metrics, nfl_name_lookup = calculate_opportunity_metrics(weekly_reg, snaps_reg, pbp_reg)
        print(f"Calculated metrics for {len(metrics)} players")
        print(f"QB grades for {len(qb_grades)} teams")
        print(f"Using {season_year} season data")
    else:
        qb_grades = {}
        metrics = {}
        nfl_name_lookup = {}
        season_year = None
        print("Using placeholder data (nfl_data_py not available)")
    
    # Generate suggested adjustments
    suggestions = generate_suggested_adjustments(players, metrics, qb_grades)
    
    # Compute team QBs and handcuffs
    team_qbs = compute_team_qb(players)
    handcuffs = compute_handcuffs_and_committee(players, metrics)
    
    # Update players with new fields
    updated_count = 0
    matched_count = 0
    for p in players:
        player = p['player']
        pos = p['pos']
        team = p.get('team', '')
        
        # Add season year label
        p['stats_season'] = season_year if season_year else None
        
        # Try to find player in NFL data with better name matching
        matched_name = None
        if player in metrics:
            matched_name = player
        else:
            # Try normalized name matching
            matched_name = find_best_name_match(player, nfl_name_lookup)
        
        # Add opportunity metrics and counting stats
        if matched_name and matched_name in metrics:
            m = metrics[matched_name]
            p['snap_share'] = m['snap_share']
            p['route_share'] = m['route_share']
            p['carry_share'] = m['carry_share']
            p['target_share'] = m['target_share']
            p['rz_share'] = m['rz_share']
            p['expected_ppg'] = m['expected_ppg']
            p['actual_ppg'] = m['actual_ppg']
            p['games_played'] = m['games_played']
            
            # Counting stats
            p['rush_att'] = m['rush_att']
            p['rush_yds'] = m['rush_yds']
            p['rush_td'] = m['rush_td']
            p['rec'] = m['rec']
            p['rec_yds'] = m['rec_yds']
            p['rec_td'] = m['rec_td']
            p['pass_yds'] = m['pass_yds']
            p['pass_td'] = m['pass_td']
            
            # Sample note
            if m['games_played'] < 10:
                p['sample_note'] = f"{m['games_played']} games ({season_year} season)" if season_year else f"{m['games_played']} games"
            else:
                p['sample_note'] = f"{m['games_played']} games ({season_year} season)" if season_year else f"{m['games_played']} games"
            
            matched_count += 1
        else:
            # Rookies / no data
            p['snap_share'] = 0
            p['route_share'] = 0
            p['carry_share'] = 0
            p['target_share'] = 0
            p['rz_share'] = 0
            p['expected_ppg'] = 0
            p['actual_ppg'] = 0
            p['games_played'] = 0
            p['rush_att'] = 0
            p['rush_yds'] = 0
            p['rush_td'] = 0
            p['rec'] = 0
            p['rec_yds'] = 0
            p['rec_td'] = 0
            p['pass_yds'] = 0
            p['pass_td'] = 0
            
            if p.get('model_path') == 'ROOKIE ENGINE':
                p['sample_note'] = "Rookie, no NFL sample"
            else:
                p['sample_note'] = "No stats match found"
        
        # Add QB situation
        if pos in ['WR', 'TE', 'RB'] and team in qb_grades:
            p['qb_situation'] = qb_grades[team]
        else:
            p['qb_situation'] = ""
        
        # Add role
        p['role'] = determine_role(player, pos, metrics)
        
        # Add team QB
        p['team_qb'] = team_qbs.get(team, "") if team else ""
        
        # Add handcuff/committee mates (RBs only)
        if pos == 'RB':
            p['handcuff'] = ", ".join(handcuffs.get(player, [])) if player in handcuffs else ""
        else:
            p['handcuff'] = ""
        
        # Add age if available
        if rosters is not None:
            age = get_player_age(rosters, player)
            p['age'] = age if age else None
        else:
            p['age'] = None
        
        # Calculate opportunity score for lens (high usage + low ADP = high opp score)
        if matched_name and matched_name in metrics:
            m = metrics[matched_name]
            usage_score = 0
            if pos == 'RB':
                usage_score = m['carry_share'] + m['snap_share'] * 0.5
            elif pos in ['WR', 'TE']:
                usage_score = m['target_share'] + m['snap_share'] * 0.3
            
            adp = p['adp']
            adp_penalty = max(0, (150 - adp) / 150) * 100
            p['opp_score'] = round(usage_score + adp_penalty, 1)
        else:
            p['opp_score'] = 0
        
        updated_count += 1
    
    # Add suggested adjustments to data
    data['suggested_adjustments'] = [
        {'player': s[0], 'adjustment': s[1], 'reason': s[2]} 
        for s in suggestions
    ]
    
    # Save updated players.json
    with open(PLAYERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\nUpdated {updated_count} players")
    print(f"Matched {matched_count} players with NFL stats")
    if season_year:
        print(f"Stats are from {season_year} regular season")
    print(f"\nGenerated {len(suggestions)} suggested rating adjustments:")
    for player, adj, reason, _ in suggestions:
        print(f"  {player:25s} {adj:+3.0f} - {reason}")
    
    # Report unmatched players
    unmatched = [p['player'] for p in players if p.get('model_path') != 'ROOKIE ENGINE' and p.get('games_played', 0) == 0 and p['pos'] not in ['K', 'DST']]
    if unmatched:
        print(f"\nCould not match {len(unmatched)} non-rookie players:")
        for name in unmatched[:10]:
            print(f"  {name}")
        if len(unmatched) > 10:
            print(f"  ... and {len(unmatched) - 10} more")
    
    print(f"\nSaved to {PLAYERS_JSON}")


if __name__ == '__main__':
    main()

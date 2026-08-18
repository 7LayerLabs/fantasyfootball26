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
            
            # Try weekly data, but if it fails, try seasonal player stats from nflverse-data releases
            weekly_reg = None
            try:
                weekly = nfl.import_weekly_data([year], downcast=False)
                weekly_reg = weekly[weekly['season_type'] == 'REG'].copy()
                print(f"Loaded weekly data for {year}")
            except Exception as weekly_err:
                print(f"Weekly data unavailable for {year}: {weekly_err}")
                print(f"Attempting to load seasonal player stats from nflverse-data releases...")
                try:
                    # Load from nflverse-data release (parquet preferred, fallback to CSV)
                    url = f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_{year}.parquet'
                    seasonal = pd.read_parquet(url)
                    print(f"Successfully loaded seasonal player stats for {year} from nflverse-data")
                    # The seasonal format is already aggregated by player/season, which is what we need
                    weekly_reg = seasonal
                except Exception as seasonal_err:
                    print(f"Seasonal stats also unavailable: {seasonal_err}")
                    raise seasonal_err
            
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
    if not isinstance(name, str) or pd.isna(name):
        return ""
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
    name_parts = normalized.split()
    if len(name_parts) == 0:
        return None
    
    last_name = name_parts[-1]
    matches = []
    for p in nfl_players:
        p_parts = p.split()
        if len(p_parts) > 0 and p_parts[-1] == last_name:
            matches.append(p)
    
    if len(matches) == 1:
        return nfl_players[matches[0]]
    
    return None


def calculate_opportunity_metrics(weekly_reg, snaps_reg, pbp_reg):
    """Calculate per-player opportunity metrics and counting stats."""
    if weekly_reg is None or pbp_reg is None:
        return {}
    
    metrics = {}
    
    # Check if data is seasonal (already aggregated) or weekly (needs aggregation)
    is_seasonal = 'games' in weekly_reg.columns and 'week' not in weekly_reg.columns
    
    # Build a normalized name lookup for NFL players
    nfl_player_lookup = {}
    for _, row in weekly_reg[['player_display_name']].drop_duplicates().iterrows():
        nfl_name = row['player_display_name']
        normalized = normalize_name(nfl_name)
        nfl_player_lookup[normalized] = nfl_name
    
    if is_seasonal:
        # Data is already aggregated by season - use it directly
        print("Using seasonal data (already aggregated)")
        player_weekly = weekly_reg.copy()
        player_weekly['week'] = player_weekly.get('games', 0)  # Use games as a proxy for counting
        player_weekly.rename(columns={'games': 'week'}, inplace=True)
    else:
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
    if is_seasonal:
        team_totals = player_weekly.groupby('recent_team').agg({
            'carries': 'sum',
            'targets': 'sum'
        }).reset_index()
        team_totals.columns = ['team', 'team_carries', 'team_targets']
    else:
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
        
        # Skip if player name is missing
        if not isinstance(player, str) or pd.isna(player):
            continue
            
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
        
        # Get carries, targets, etc. - ensure we convert to scalar
        carries = int(row['carries']) if pd.notna(row['carries']) else 0
        targets = int(row['targets']) if pd.notna(row['targets']) else 0
        rushing_yards = int(row['rushing_yards']) if pd.notna(row['rushing_yards']) else 0
        rushing_tds = int(row['rushing_tds']) if pd.notna(row['rushing_tds']) else 0
        receptions = int(row['receptions']) if pd.notna(row['receptions']) else 0
        receiving_yards = int(row['receiving_yards']) if pd.notna(row['receiving_yards']) else 0
        receiving_tds = int(row['receiving_tds']) if pd.notna(row['receiving_tds']) else 0
        passing_yards = int(row['passing_yards']) if pd.notna(row['passing_yards']) else 0
        passing_tds = int(row['passing_tds']) if pd.notna(row['passing_tds']) else 0
        
        # Calculate shares
        if pos == 'RB':
            carry_share = round(100 * carries / team_carries, 1) if team_carries > 0 else 0
            # Route share approximation for RBs: targets / team_targets * 0.8
            route_share = round(100 * targets / team_targets * 0.8, 1) if team_targets > 0 and targets > 0 else 0
        else:
            carry_share = 0
            # Route share approximation for WR/TE: targets / team_targets
            route_share = round(100 * targets / team_targets, 1) if team_targets > 0 and targets > 0 else 0
        
        target_share = round(100 * targets / team_targets, 1) if team_targets > 0 and targets > 0 else 0
        
        # Red zone share (total touches in RZ) - use abbreviated name
        player_abbrev = player.split()[0][0] + '.' + player.split()[-1]
        rz_share = 0
        if player_abbrev in rz_carries.index:
            rz_share += rz_carries[player_abbrev]
        if player_abbrev in rz_targets.index:
            rz_share += rz_targets[player_abbrev]
        rz_share = round(rz_share, 0)
        
        # Expected fantasy points (simple volume-based proxy)
        try:
            if 'games' in player_weekly.columns:
                games = int(row['games']) if pd.notna(row['games']) else 1
            elif 'week' in player_weekly.columns:
                games = int(row['week']) if pd.notna(row['week']) else 1
            else:
                games = 1
        except (ValueError, TypeError):
            games = 1
        
        if games == 0:
            games = 1
        
        # For seasonal data, fantasy_points_ppr might not exist
        if 'fantasy_points_ppr' in row.index and pd.notna(row['fantasy_points_ppr']):
            actual_ppg = row['fantasy_points_ppr'] / games
        else:
            # Calculate PPR points manually
            ppr_points = (rushing_yards * 0.1 + rushing_tds * 6 + 
                          receptions * 1 + receiving_yards * 0.1 + receiving_tds * 6 +
                          passing_yards * 0.04 + passing_tds * 4)
            actual_ppg = ppr_points / games
        
        # xFP proxy: based on usage
        if pos == 'RB':
            expected_ppg = (carries / games) * 0.1 + (targets / games) * 0.5
        elif pos in ['WR', 'TE']:
            expected_ppg = (targets / games) * 0.5
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
            'games_played': int(games),
            # Counting stats
            'rush_att': int(carries) if pos in ['RB', 'QB'] else 0,
            'rush_yds': int(rushing_yards) if pos in ['RB', 'QB'] else 0,
            'rush_td': int(rushing_tds) if pos in ['RB', 'QB'] else 0,
            'rec': int(receptions) if pos in ['RB', 'WR', 'TE'] else 0,
            'rec_yds': int(receiving_yards) if pos in ['RB', 'WR', 'TE'] else 0,
            'rec_td': int(receiving_tds) if pos in ['RB', 'WR', 'TE'] else 0,
            'pass_yds': int(passing_yards) if pos == 'QB' else 0,
            'pass_td': int(passing_tds) if pos == 'QB' else 0
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


def calculate_rate_vs_career(weekly_reg, season_year, pbp_reg=None):
    """Calculate rate-vs-career analytics for QBs and skill positions.
    
    Career definition: All regular seasons from 2013 through season_year (inclusive).
    Last year = season_year only.
    
    Returns dict keyed by player_display_name with:
    - QB: pass_td_rate, pass_td_rate_career, pass_td_rate_spike, int_rate, int_rate_career, ypa, ypa_career
    - WR/TE/RB: rec_td_rate, rec_td_rate_career, rec_td_rate_spike
    - RB: rush_td_rate, rush_td_rate_career, rush_td_rate_spike
    """
    if not NFL_DATA_AVAILABLE or season_year is None or weekly_reg is None:
        return {}
    
    print(f"Calculating rate-vs-career analytics using {season_year} as last year...")
    
    # Check if weekly_reg is seasonal (already aggregated) or weekly (needs aggregation)
    is_seasonal = 'games' in weekly_reg.columns and 'week' not in weekly_reg.columns
    
    if is_seasonal:
        print(f"Data is seasonal format (already aggregated by season)")
        last_year_stats = weekly_reg.copy()
    else:
        print(f"Data is weekly format (aggregating by player)")
        # Group by player for last year (season_year) - weekly format
        last_year_stats = weekly_reg.groupby(['player_display_name', 'position']).agg({
            'attempts': 'sum',
            'completions': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'interceptions': 'sum',
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_tds': 'sum'
        }).reset_index()
    
    # Load career data from seasonal stats (2013 through season_year)
    career_years = list(range(2013, season_year + 1))
    print(f"Loading career data (seasonal) from {career_years[0]} to {season_year}...")
    
    try:
        # Load all career years from nflverse-data releases
        career_dfs = []
        for year in career_years:
            try:
                url = f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_{year}.parquet'
                df = pd.read_parquet(url)
                career_dfs.append(df)
            except Exception as e:
                print(f"  Warning: Could not load {year}: {e}")
                continue
        
        if not career_dfs:
            print("Warning: No career data loaded, skipping rate-vs-career calculation")
            return {}
        
        career_all = pd.concat(career_dfs, ignore_index=True)
        print(f"Loaded career data: {len(career_dfs)} seasons, {len(career_all)} player-season records")
        
        # Aggregate career stats across all seasons
        career_stats = career_all.groupby(['player_display_name', 'position']).agg({
            'attempts': 'sum',
            'completions': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'passing_interceptions': 'sum',
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_tds': 'sum'
        }).reset_index()
        
        # Rename columns to match expected format
        career_stats.rename(columns={'passing_interceptions': 'interceptions'}, inplace=True)
        
    except Exception as e:
        print(f"Warning: Could not load full career data: {e}")
        return {}
    
    rate_stats = {}
    
    # Build normalized name lookup
    nfl_player_lookup = {}
    for _, row in last_year_stats[['player_display_name']].drop_duplicates().iterrows():
        nfl_name = row['player_display_name']
        normalized = normalize_name(nfl_name)
        nfl_player_lookup[normalized] = nfl_name
    
    # Process each player from last year
    for _, row in last_year_stats.iterrows():
        player = row['player_display_name']
        pos = row['position']
        
        # Get career stats
        career_row = career_stats[career_stats['player_display_name'] == player]
        if career_row.empty:
            continue
        career_row = career_row.iloc[0]
        
        player_rates = {}
        
        if pos == 'QB':
            # QB rates
            pass_att_last = row['attempts']
            pass_td_last = row.get('passing_tds', 0)
            int_last = row.get('interceptions', 0)
            pass_yds_last = row.get('passing_yards', 0)
            
            pass_att_career = career_row['attempts']
            pass_td_career = career_row['passing_tds']
            int_career = career_row['interceptions']
            pass_yds_career = career_row['passing_yards']
            
            if pass_att_last >= 100:  # Minimum threshold for last year
                # TD rate
                pass_td_rate = 100.0 * pass_td_last / pass_att_last if pass_att_last > 0 else 0
                pass_td_rate_career = 100.0 * pass_td_career / pass_att_career if pass_att_career > 0 else 0
                pass_td_rate_spike = pass_td_rate - pass_td_rate_career
                
                # INT rate
                int_rate = 100.0 * int_last / pass_att_last if pass_att_last > 0 else 0
                int_rate_career = 100.0 * int_career / pass_att_career if pass_att_career > 0 else 0
                
                # Y/A
                ypa = pass_yds_last / pass_att_last if pass_att_last > 0 else 0
                ypa_career = pass_yds_career / pass_att_career if pass_att_career > 0 else 0
                
                player_rates = {
                    'pass_td_rate': round(pass_td_rate, 2),
                    'pass_td_rate_career': round(pass_td_rate_career, 2),
                    'pass_td_rate_spike': round(pass_td_rate_spike, 2),
                    'int_rate': round(int_rate, 2),
                    'int_rate_career': round(int_rate_career, 2),
                    'ypa': round(ypa, 2),
                    'ypa_career': round(ypa_career, 2),
                    'pass_att_last': int(pass_att_last),
                    'pass_td_last': int(pass_td_last),
                    'pass_att_career': int(pass_att_career),
                    'pass_td_career': int(pass_td_career)
                }
        
        elif pos in ['WR', 'TE']:
            # Receiving TD rate
            targets_last = row.get('targets', 0) if row.get('targets', 0) > 0 else row.get('receptions', 0)
            rec_td_last = row.get('receiving_tds', 0)
            
            targets_career = career_row.get('targets', 0) if career_row.get('targets', 0) > 0 else career_row.get('receptions', 0)
            rec_td_career = career_row.get('receiving_tds', 0)
            
            if targets_last >= 20:  # Minimum threshold
                rec_td_rate = 100.0 * rec_td_last / targets_last if targets_last > 0 else 0
                rec_td_rate_career = 100.0 * rec_td_career / targets_career if targets_career > 0 else 0
                rec_td_rate_spike = rec_td_rate - rec_td_rate_career
                
                player_rates = {
                    'rec_td_rate': round(rec_td_rate, 2),
                    'rec_td_rate_career': round(rec_td_rate_career, 2),
                    'rec_td_rate_spike': round(rec_td_rate_spike, 2)
                }
        
        elif pos == 'RB':
            # Receiving TD rate
            targets_last = row.get('targets', 0) if row.get('targets', 0) > 0 else row.get('receptions', 0)
            rec_td_last = row.get('receiving_tds', 0)
            
            targets_career = career_row.get('targets', 0) if career_row.get('targets', 0) > 0 else career_row.get('receptions', 0)
            rec_td_career = career_row.get('receiving_tds', 0)
            
            # Rushing TD rate
            rush_att_last = row.get('carries', 0)
            rush_td_last = row.get('rushing_tds', 0)
            
            rush_att_career = career_row.get('carries', 0)
            rush_td_career = career_row.get('rushing_tds', 0)
            
            player_rates = {}
            
            if targets_last >= 20:  # Minimum threshold
                rec_td_rate = 100.0 * rec_td_last / targets_last if targets_last > 0 else 0
                rec_td_rate_career = 100.0 * rec_td_career / targets_career if targets_career > 0 else 0
                rec_td_rate_spike = rec_td_rate - rec_td_rate_career
                
                player_rates.update({
                    'rec_td_rate': round(rec_td_rate, 2),
                    'rec_td_rate_career': round(rec_td_rate_career, 2),
                    'rec_td_rate_spike': round(rec_td_rate_spike, 2)
                })
            
            if rush_att_last >= 50:  # Minimum threshold
                rush_td_rate = 100.0 * rush_td_last / rush_att_last if rush_att_last > 0 else 0
                rush_td_rate_career = 100.0 * rush_td_career / rush_att_career if rush_att_career > 0 else 0
                rush_td_rate_spike = rush_td_rate - rush_td_rate_career
                
                player_rates.update({
                    'rush_td_rate': round(rush_td_rate, 2),
                    'rush_td_rate_career': round(rush_td_rate_career, 2),
                    'rush_td_rate_spike': round(rush_td_rate_spike, 2)
                })
        
        if player_rates:
            rate_stats[player] = player_rates
    
    print(f"Calculated rate-vs-career for {len(rate_stats)} players")
    return rate_stats


def derive_weekly_from_pbp(pbp_reg):
    """Derive weekly-style stats from play-by-play data when weekly data is unavailable."""
    if pbp_reg is None:
        return None
    
    try:
        # Aggregate QB stats from PBP
        qb_stats = pbp_reg[pbp_reg['passer_player_name'].notna()].groupby('passer_player_name').agg({
            'pass_attempt': 'sum',
            'complete_pass': 'sum',
            'pass_touchdown': 'sum',
            'interception': 'sum',
            'passing_yards': 'sum'
        }).reset_index()
        qb_stats.columns = ['player_display_name', 'attempts', 'completions', 'passing_tds', 'interceptions', 'passing_yards']
        qb_stats['position'] = 'QB'
        qb_stats['targets'] = 0
        qb_stats['receptions'] = 0
        qb_stats['receiving_tds'] = 0
        qb_stats['carries'] = 0
        qb_stats['rushing_tds'] = 0
        
        # Aggregate receiver stats from PBP
        rec_stats = pbp_reg[pbp_reg['receiver_player_name'].notna()].groupby('receiver_player_name').agg({
            'pass_attempt': 'sum',
            'complete_pass': 'sum',
            'pass_touchdown': 'sum'
        }).reset_index()
        rec_stats.columns = ['player_display_name', 'targets', 'receptions', 'receiving_tds']
        # Infer position from targets (approximate - could be improved)
        rec_stats['position'] = 'WR'  # Default; will need manual correction for TE/RB
        rec_stats['attempts'] = 0
        rec_stats['completions'] = 0
        rec_stats['passing_tds'] = 0
        rec_stats['interceptions'] = 0
        rec_stats['passing_yards'] = 0
        rec_stats['carries'] = 0
        rec_stats['rushing_tds'] = 0
        
        # Aggregate rusher stats from PBP
        rush_stats = pbp_reg[pbp_reg['rusher_player_name'].notna()].groupby('rusher_player_name').agg({
            'rush_attempt': 'sum',
            'rush_touchdown': 'sum'
        }).reset_index()
        rush_stats.columns = ['player_display_name', 'carries', 'rushing_tds']
        rush_stats['position'] = 'RB'  # Default
        rush_stats['attempts'] = 0
        rush_stats['completions'] = 0
        rush_stats['passing_tds'] = 0
        rush_stats['interceptions'] = 0
        rush_stats['passing_yards'] = 0
        rush_stats['targets'] = 0
        rush_stats['receptions'] = 0
        rush_stats['receiving_tds'] = 0
        
        # Combine all stats
        import pandas as pd
        combined = pd.concat([qb_stats, rec_stats, rush_stats], ignore_index=True)
        
        return combined
    except Exception as e:
        print(f"Error deriving weekly stats from PBP: {e}")
        return None


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
        
        # Calculate rate-vs-career analytics
        rate_vs_career = calculate_rate_vs_career(weekly_reg, season_year, pbp_reg)
    else:
        qb_grades = {}
        metrics = {}
        nfl_name_lookup = {}
        season_year = None
        rate_vs_career = {}
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
        
        # Add rate-vs-career analytics
        if matched_name and matched_name in rate_vs_career:
            rate_stats = rate_vs_career[matched_name]
            # Add all rate stats for this player
            for key, value in rate_stats.items():
                p[key] = value
        else:
            # Initialize rate-vs-career fields based on position
            if pos == 'QB':
                p['pass_td_rate'] = None
                p['pass_td_rate_career'] = None
                p['pass_td_rate_spike'] = None
                p['int_rate'] = None
                p['int_rate_career'] = None
                p['ypa'] = None
                p['ypa_career'] = None
            elif pos in ['WR', 'TE']:
                p['rec_td_rate'] = None
                p['rec_td_rate_career'] = None
                p['rec_td_rate_spike'] = None
            elif pos == 'RB':
                p['rec_td_rate'] = None
                p['rec_td_rate_career'] = None
                p['rec_td_rate_spike'] = None
                p['rush_td_rate'] = None
                p['rush_td_rate_career'] = None
                p['rush_td_rate_spike'] = None
        
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

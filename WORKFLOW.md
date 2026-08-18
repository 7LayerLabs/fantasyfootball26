# FF26 Draft Kit Workflow

## Overview

The FF26 draft kit has three main components that stay synchronized through `players.json`:

1. **Excel Engine**: Full workbook with ranking formulas, Manual Adjustments, and Player Detail sheet
2. **Live-Draft Cheat Sheet**: `draft-board.html` with clickable player cards showing detailed profiles
3. **Player Data**: `scripts/players.json` is the canonical source for all player information

## Data Flow

```
players.json (canonical)
    ├─> build.py ──> Excel workbook with Player Detail sheet
    ├─> rebuild_board_data.py ──> board_data.json
    └─> bake_state.py ──> draft-board.html (live cheat sheet)
```

## Keeping Everything in Sync

### 1. Update Player Data

When NFL data changes (new stats, injuries, role changes):

```bash
# Fetch latest NFL data and update players.json
python scripts/add_opportunity_analytics.py

# This script:
# - Fetches 2025 (or 2024) regular season data from nflverse
# - Calculates opportunity metrics (snap/target/carry shares)
# - Adds counting stats (rush/rec/pass stats)
# - Computes team QB, handcuffs, and ages
# - Generates suggested rating adjustments
# - Updates players.json with all fields
```

### 2. Rebuild Excel Workbook

```bash
# Generate the Excel file with Player Detail sheet
python scripts/build.py

# This creates:
# - All ranking sheets (FINAL Master, Top 200, etc.)
# - Player Detail sheet with full profiles
# - Draft Engine with formulas
# - Manual Adjustments (editable)
```

### 3. Rebuild Cheat Sheet

```bash
# Update board data from players.json
python scripts/rebuild_board_data.py

# Re-bake the HTML cheat sheet
python scripts/bake_state.py

# This creates:
# - draft-board.html with updated player cards
# - Includes all opportunity, situation, and counting stats
# - Player cards open on click with full profiles
```

## Player Detail Fields

Both the Excel "Player Detail" sheet and the cheat-sheet player cards show:

### Basic Info
- Position, Team, Bye Week, Age
- Base Rating, ADP, Overall Rank

### Situation
- Role (feature / committee / handcuff / unclear)
- QB Situation (elite / average / weakness / unproven)
- Team QB name
- Committee/Handcuff mates

### Opportunity (2024 season)
- Games Played
- Snap Share %
- Target Share % (WR/TE/RB)
- Carry Share % (RB)
- Red Zone Touches

### Counting Stats (2024 season)
- Rush: Attempts / Yards / TDs
- Receiving: Receptions / Yards / TDs
- Passing: Yards / TDs (QB)
- Total PPR Points

### Rate vs Career (NEW - 2024 season vs career)
- **QB**: Last Yr TD% / Career TD% / Spike (pp), Last Yr INT% / Career INT%, Last Yr Y/A / Career Y/A
- **WR/TE**: Rec TD Rate / Career Rec TD Rate / Spike (pp)
- **RB**: Rec TD Rate / Career Rec TD Rate / Spike (pp), Rush TD Rate / Career Rush TD Rate / Spike (pp)
- Spike = Last Year Rate - Career Rate (percentage points)
- Shows "SPIKE" if last year significantly above career, "FAIR" if near career, "COLD" if below career
- Rookies / unmatched: shown as blank or "No NFL sample"

### Scouting
- Expectation: What to expect in 2026
- Why We Rank Here: Rationale
- Main Risk: Downside scenarios

## Notes

- **Original base ratings are never changed** by the analytics scripts. They are preserved in `players.json`.
- **Suggested adjustments** are stored separately in the `suggested_adjustments` array.
- **Rookies** show "Rookie, no NFL sample" (no invented stats).
- **Unmatched players** show "No stats match found" if name matching fails.
- **Season label**: Stats are labeled with the season year (2024 or 2025) so you know which data is current.
- **No scraping**: All data comes from legal open sources (nflverse / nfl_data_py).

## Manual Adjustments

If you want to apply a suggested adjustment:

1. Open the Excel file
2. Go to "Manual Adjustments" sheet
3. Find the player
4. Add the adjustment value to the appropriate column (Injury Adj, Role Adj, or Other Adj)
5. Add a note in the "News / Reason" column
6. Rebuild cheat sheet to reflect the change

The adjustment will flow through the Draft Engine formulas automatically.

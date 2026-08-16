# Workflow Guide: Refreshing ADP and Rebuilding the Board

This guide explains how to keep the 2026 FF26 draft board current during draft season.

## Quick Reference

```bash
# 1. Refresh ADP (updates scripts/players.json)
python3 scripts/refresh_adp.py

# 2. Rebuild Excel (Windows only, or manually in Excel)
# Windows: scripts/recalc.ps1
# Mac/Linux: Open Excel, press F9 to recalc, save and close

# 3. Extract computed values
python3 scripts/extract_board.py

# 4. Bake the HTML board
python3 scripts/bake_state.py

# Result: draft-board.html is now up to date
```

## Detailed Steps

### Step 1: Refresh Market ADP

Market ADP changes weekly. Update it without touching base ratings:

```bash
cd /workspace
python3 scripts/refresh_adp.py
```

The script updates only the `adp` field in `scripts/players.json`. It preserves:
- All base ratings (Derek's opinions)
- All confidence levels
- All expectation/why/risk prose
- All manual adjustments (injuries, roles)

**ADP Sources:**

The script tries these sources in order:

1. **Manual file** (recommended for reliability):
   - Create `scripts/manual_adp.json` with current values:
   ```json
   {
     "Puka Nacua": 2.8,
     "Bijan Robinson": 1.9,
     "Ja'Marr Chase": 3.1,
     ...
   }
   ```
   - Get data from Sleeper, FantasyPros, Underdog, or your league's platform

2. **Sleeper API** (public, free):
   - The script attempts to fetch from Sleeper's public endpoints
   - May need adjustment for 2026 season structure

3. **FantasyPros API** (requires key):
   - Implement in the script if you have an API key
   - Or scrape their public consensus page (check their ToS)

**Checking the update:**

```bash
# See what changed
git diff scripts/players.json | grep '"adp"'

# Verify base ratings unchanged
git diff scripts/players.json | grep '"base"'
# Should show no changes (or only new optional slot-ins)
```

### Step 2: Rebuild the Excel Workbook

The Excel file contains all the formulas, VORPs, rankings, and QA checks. After updating ADP in `players.json`, rebuild the workbook:

```bash
python3 scripts/build.py
```

This creates/updates `2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx` in the workspace root.

**Important:** The file is created but Excel formulas need to be calculated. You have two options:

#### Option A: Windows with Excel (recalc.ps1)

```powershell
# From PowerShell
cd scripts
.\recalc.ps1
```

This opens Excel via COM, forces a full recalc, saves, and closes.

#### Option B: Manual (Mac/Linux or without PowerShell)

1. Open `2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx` in Excel
2. Press `Ctrl+Alt+F9` (Windows) or `Cmd+Opt+Shift+F9` (Mac) for full recalc
3. Check the "QA Checks" tab - must show "ALL CHECKS PASS"
4. Save and close

**If QA checks fail:**
- Check for formula errors in the Draft Engine tab
- Verify player count is 230
- Check that K/DST are gated to overall 131-150

### Step 3: Extract Computed Values

The HTML draft board embeds a snapshot of the Excel calculations. Extract them:

```bash
python3 scripts/extract_board.py
```

This reads the recalculated workbook and writes `scripts/board_data.json` with:
- All 230 players in overall rank order
- Computed ratings, VORPs, draft scores
- Proj points, tiers, confidence
- Expectation and risk prose

**Verify the extract:**

```bash
# Check player count
python3 -c "import json; print(len(json.load(open('scripts/board_data.json'))))"
# Should print: 230

# Check top player
head -20 scripts/board_data.json
```

### Step 4: Bake the HTML Draft Board

Inject the board data into the HTML template:

```bash
python3 scripts/bake_state.py
```

This creates `draft-board.html` in the workspace root, ready to deploy to dbtech45.com/ff26.

**Storage version:** If you've changed overall ranks (via injury adjustments), bump the `draftboard2026-v6` version in `scripts/board_template.html` before baking. This forces browsers to reset saved draft state.

## Common Scenarios

### Weekly ADP refresh (no other changes)

```bash
python3 scripts/refresh_adp.py
python3 scripts/build.py
# Recalc Excel manually or via recalc.ps1
python3 scripts/extract_board.py
python3 scripts/bake_state.py
```

### Injury adjustment (manual edit in Excel)

1. Open the workbook
2. Go to "Manual Adjustments" tab
3. Edit injury/role adj columns (blue cells)
4. Save
5. Run extract + bake:
   ```bash
   python3 scripts/extract_board.py
   python3 scripts/bake_state.py
   ```

### Changing a player's expectation/why/risk prose

Edit `scripts/players.json` directly, then rebuild:

```bash
# Edit players.json
python3 scripts/build.py
# Recalc Excel
python3 scripts/extract_board.py
python3 scripts/bake_state.py
```

### Adding camp watch names

Edit `scripts/camp_watch.json` to add names. Do NOT add them to `players.json` with fake base ratings.

## Files Reference

| File | Role | Edit? |
|------|------|-------|
| `scripts/players.json` | Canonical 230-player input | Yes (ADP, prose) |
| `scripts/build.py` | Generates Excel from players.json | No |
| `2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx` | Calculation engine | Manual adjustments only |
| `scripts/extract_board.py` | Pulls computed values from Excel | No |
| `scripts/board_data.json` | Extracted rankings | No (generated) |
| `scripts/bake_state.py` | Creates HTML board | No |
| `scripts/board_template.html` | HTML template | Rarely (storage version) |
| `draft-board.html` | Final draft board | No (generated) |
| `scripts/camp_watch.json` | Camp buzz names | Yes |

## Requirements

```bash
pip install -r requirements.txt
# installs: openpyxl, requests
```

For Windows Excel recalc: PowerShell + Excel COM (PowerShell 5.1+, Excel 2016+)

## Troubleshooting

**"No ADP source available"**
- Create `scripts/manual_adp.json` with current values
- Or implement Sleeper/FantasyPros API in `refresh_adp.py`

**"Player count mismatch" in extract**
- Check that build.py ran successfully
- Verify `players.json` has exactly 230 players

**QA checks fail after build**
- Open Excel and check the "QA Checks" tab for specific errors
- Common: formula errors in Draft Engine, rank conflicts, missing players

**draft-board.html not showing latest data**
- Clear browser cache or bump storage version in board_template.html
- Verify bake_state.py ran without errors

**Base ratings changed unintentionally**
- Run `git diff scripts/players.json | grep '"base"'`
- If base changed, restore from git: `git checkout scripts/players.json`
- Then re-apply only the ADP updates

## Philosophy Reminder

**Never change:**
- Base ratings (Derek's opinionated layer)
- Confidence levels
- Model paths (RATE-ADJUSTED VETERAN, ROOKIE ENGINE, etc.)

**Safe to change:**
- Market ADP
- Team/bye (if sourced from API)
- Manual adjustments (injuries, roles)
- Expectation/why/risk prose (to match reality)

Draft Edge = ADP - Overall Rank is SUPPOSED to move when ADP moves and opinions stay put. That's the whole point.

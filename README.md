# 2026 Fantasy Football Draft Engine

10-team full-PPR draft system: an Excel workbook that does the math, and a one-file web app for running live drafts.

## The files

| File | What it is |
|------|-----------|
| `2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx` | The engine. 16 tabs, one canonical data chain: LIVE SOURCE (223 players) + Manual Adjustments feed the Draft Engine tab, and every rankings tab (FINAL Master, Top 200, position tabs, K, DST) is a live formula view of it. Zero copied rankings. QA Checks tab must show ALL CHECKS PASS. |
| `2026_Fantasy_Football_Draft_Engine_CLEAN_FINAL.xlsx` | The original source workbook the engine was rebuilt from (static copies, kept for reference). |
| `draft-board.html` | The draft app. One file, no server, works offline. Open it in a browser. |

## Using the workbook

- Edit blue cells only: League Config settings, Manual Adjustments (injury/role tweaks), Market ADP in LIVE SOURCE.
- One injury adjustment cascades everywhere: rating, positional rank, overall rank, VORP, draft score, every view tab.
- K and DST are hard-gated to overall ranks 131-150 so they never pollute the draft board early.
- Check the QA Checks tab after any edit: 13 checks, all must say PASS.

## Using the draft app

- Set Teams and My Slot in the header when your draft assigns them.
- Every pick: type a few letters of the name, **Enter** = taken by someone else, **Shift+Enter** = your pick. **Ctrl+Z** undoes.
- **Out** button (red) = injured player: removes him from every suggestion without counting as a draft pick.
- Draft Next card has six lens buttons (Best Pick / Value / Sleeper / Rookie / Safe / Upside), all driven by the workbook's own ratings. Ownership caps apply everywhere: no third QB or TE, no second K or DST, and K/DST can never be a "sleeper".
- My Team So Far grades your roster against the league live (snake math attributes every pick to a team).
- State saves in the browser; Reset draft starts over.

## Keeping app and workbook in sync (scripts/)

The app embeds a snapshot of the workbook's computed values. After changing the workbook (e.g. a new injury adjustment):

1. `recalc.ps1` - opens the workbook in Excel, full recalc, saves (QA values refresh).
2. `extract_board.py` - pulls the computed values into `board_data.json`.
3. `bake_state.py` - injects the data into `board_template.html` and writes `draft-board.html`. Bump the storage KEY version in the template on every resync (saved draft states key on overall rank and must not survive a data change).

`build.py` regenerates the entire workbook from scratch (formulas, QA tab, formatting). Scripts contain absolute paths from the original machine; adjust before running elsewhere.

Built 2026-08-11. Player pool: 223 (32 QB, 50 RB, 70 WR, 27 TE, 12 K, 32 DST). Ratings source: FantasyPros-derived model, PPR.

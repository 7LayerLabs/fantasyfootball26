"""Build 2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx.

One canonical chain: LIVE SOURCE (inputs) + Manual Adjustments (edits)
-> Draft Engine (all math) -> every other tab is a formula view.
Row-aligned tabs (LIVE SOURCE / Manual Adjustments / Draft Engine) share
identical row order, so cross-sheet refs are direct, not SUMIFS.
"""
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule

SCRATCH = r"C:\Users\derek\AppData\Local\Temp\claude\C--Users-derek\51be7128-2b08-4038-953f-b27b86e2ee5a\scratchpad"
OUT = r"C:\Users\derek\Downloads\Documents\2026_Fantasy_Football_Draft_Engine_100_PERCENT_FIXED.xlsx"

with open(SCRATCH + r"\players.json", encoding="utf-8") as f:
    data = json.load(f)
players = data["players"]
cfg = data["config"]
# source file block order is QB, RB, TE, WR; force canonical QB, RB, WR, TE, K, DST
# (stable sort keeps rating order within each position)
POS_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DST": 5}
players.sort(key=lambda p: POS_ORDER[p["pos"]])

N = len(players)          # 223
DS = 3                    # first data row on every sheet
DE_END = DS + N - 1       # 225

# position block sheet-row ranges (fixed by construction)
blocks = {}
row = DS
for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
    n = sum(1 for p in players if p["pos"] == pos)
    blocks[pos] = (row, row + n - 1, n)
    row += n
assert row - DS == N

# ---------- styling ----------
NAVY = "1F3352"
BLUE_EDIT = "DCE9F7"      # editable cells
GRAY = "8A8F98"
GREEN = "C6EFCE"
RED = "FFC7CE"
HDR_FONT = Font(bold=True, color="FFFFFF", size=10)
HDR_FILL = PatternFill("solid", fgColor=NAVY)
TITLE_FONT = Font(bold=True, size=14, color=NAVY)
SUB_FONT = Font(italic=True, size=9, color=GRAY)
EDIT_FILL = PatternFill("solid", fgColor=BLUE_EDIT)
HELPER_FONT = Font(color=GRAY, size=8)
THIN = Border(bottom=Side(style="hair", color="D9D9D9"))

wb = openpyxl.Workbook()
wb.remove(wb.active)

def sheet(name, title, subtitle, headers, widths, tab_color=None):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = SUB_FONT
    for c, h in enumerate(headers, 1):
        cell = ws.cell(2, c) if False else ws.cell(DS - 1, c)
    # headers live on row 2 (DS-1)
    for c, h in enumerate(headers, 1):
        cell = ws.cell(DS - 1, c)
        cell.value = h
        cell.font = HDR_FONT
        cell.fill = HDR_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = ws.cell(DS, 1)
    if tab_color:
        ws.sheet_properties.tabColor = tab_color
    return ws

# NOTE: title on row 1, headers on row 2, data from row 3. Subtitle merged into A2? A2 is header row.
# Fix: put subtitle inside title cell comment-free -> shift: title row1, header row2, so subtitle goes in a title suffix.
def sheet2(name, title, headers, widths, tab_color=None):
    ws = wb.create_sheet(name)
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    for c, h in enumerate(headers, 1):
        cell = ws.cell(2, c)
        cell.value = h
        cell.font = HDR_FONT
        cell.fill = HDR_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[2].height = 28
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = f"A{DS}"
    if tab_color:
        ws.sheet_properties.tabColor = tab_color
    return ws

def numfmt(ws, cols, fmt, r1=DS, r2=DE_END):
    for col in cols:
        for r in range(r1, r2 + 1):
            ws[f"{col}{r}"].number_format = fmt

def edit_mark(ws, cols, r1=DS, r2=DE_END):
    for col in cols:
        for r in range(r1, r2 + 1):
            ws[f"{col}{r}"].fill = EDIT_FILL

TIER_F = ('=IF({0}>=95,"ELITE",IF({0}>=90,"TIER 1",IF({0}>=85,"TIER 2",'
          'IF({0}>=80,"TIER 3",IF({0}>=75,"TIER 4",IF({0}>=70,"TIER 5",'
          'IF({0}>=65,"TIER 6","TIER 7")))))))')

# =====================================================================
# 1. League Config
# =====================================================================
lc = wb.create_sheet("League Config")
lc.sheet_properties.tabColor = "2E75B6"
lc["A1"] = "League Configuration (Editable)"
lc["A1"].font = TITLE_FONT
lc["A2"] = "Blue cells are yours to edit. Everything downstream recalculates automatically."
lc["A2"].font = SUB_FONT

settings = [
    ("Teams", cfg["teams"], "League size."),
    ("Scoring", cfg["scoring"], "Player model is PPR."),
    ("Starting QB", cfg["qb"], "Per team."),
    ("Starting RB", cfg["rb"], "Per team."),
    ("Starting WR", cfg["wr"], "Per team."),
    ("Starting TE", cfg["te"], "Per team."),
    ("Starting FLEX", cfg["flex"], "RB/WR/TE."),
    ("Starting K", cfg["k"], "Per team."),
    ("Starting DST", cfg["dst"], "Per team."),
    ("Bench", cfg["bench"], "Per team."),
    ("K Draft Penalty", cfg["k_penalty"], "Higher = drafts later."),
    ("DST Draft Penalty", cfg["dst_penalty"], "Higher = drafts later."),
    ("QB 1QB Penalty", cfg["qb_penalty"], "Set lower in Superflex."),
    ("DST Gate Start", 131, "Top DSTs locked to overall 131-140."),
    ("K Gate Start", 141, "Top Ks locked to overall 141-150. Keep = DST gate + gate size."),
    ("Gate Size", 10, "How many DST/K get gated slots."),
]
for c, h in enumerate(["League Setting", "Value", "Notes"], 1):
    cell = lc.cell(3, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
r = 4
for name, val, note in settings:
    lc.cell(r, 1, name)
    lc.cell(r, 2, val).fill = EDIT_FILL
    lc.cell(r, 3, note)
    r += 1
# r == 20 now
lc.cell(21, 1, "Skill players (calc)")
lc.cell(21, 2, f'=COUNTIF(\'LIVE SOURCE\'!$A${DS}:$A${DE_END},"QB")+COUNTIF(\'LIVE SOURCE\'!$A${DS}:$A${DE_END},"RB")+COUNTIF(\'LIVE SOURCE\'!$A${DS}:$A${DE_END},"WR")+COUNTIF(\'LIVE SOURCE\'!$A${DS}:$A${DE_END},"TE")')
lc.cell(22, 1, "DST count (calc)")
lc.cell(22, 2, f'=COUNTIF(\'LIVE SOURCE\'!$A${DS}:$A${DE_END},"DST")')

# position table E3:L9
pos_hdr = ["Position", "Calc Repl Rank", "Override", "Effective Rank",
           "Replacement Points", "Scarcity Mult", "Pts Slope", "Pts Intercept"]
for c, h in enumerate(pos_hdr, 5):
    cell = lc.cell(3, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
    cell.alignment = Alignment(wrap_text=True, horizontal="center")

repl_rank_f = {
    "QB":  "=ROUND($B$4*$B$6+$B$4*0.30,0)",
    "RB":  "=ROUND($B$4*$B$7+$B$4*$B$10*0.55+$B$4*0.60,0)",
    "WR":  "=ROUND($B$4*$B$8+$B$4*$B$10*0.45+$B$4*0.80,0)",
    "TE":  "=ROUND($B$4*$B$9+$B$4*0.30,0)",
    "K":   "=ROUND($B$4*$B$11,0)",
    "DST": "=ROUND($B$4*$B$12,0)",
}
curves = {"QB": (4.5, -30), "RB": (4.2, -70), "WR": (4.2, -70),
          "TE": (3.5, -100), "K": (2.0, -40), "DST": (1.8, -50)}
for i, pos in enumerate(["QB", "RB", "WR", "TE", "K", "DST"]):
    r = 4 + i
    lc.cell(r, 5, pos)
    lc.cell(r, 6).value = repl_rank_f[pos]
    lc.cell(r, 7).fill = EDIT_FILL  # override, blank
    lc.cell(r, 8).value = f'=IF($G{r}="",$F{r},$G{r})'
    lc.cell(r, 9).value = (f"=ROUND(_xlfn.AGGREGATE(14,6,'Draft Engine'!$G${DS}:$G${DE_END}/"
                           f"('Draft Engine'!$A${DS}:$A${DE_END}=$E{r}),"
                           f"MIN($H{r},COUNTIF('Draft Engine'!$A${DS}:$A${DE_END},$E{r}))),1)")
    lc.cell(r, 10, cfg["scarcity_mult"][pos]).fill = EDIT_FILL
    lc.cell(r, 11, curves[pos][0]).fill = EDIT_FILL
    lc.cell(r, 12, curves[pos][1]).fill = EDIT_FILL
lc["E11"] = "Projected points = Pts Slope x Adjusted Rating + Pts Intercept (per position). Tune the curve here."
lc["E11"].font = SUB_FONT
for col, w in zip("ABCDEFGHIJKL", [18, 10, 44, 2, 9, 12, 9, 11, 13, 11, 9, 11]):
    lc.column_dimensions[col].width = w

# named cells
for nm, ref in [("DstStart", "$B$17"), ("KStart", "$B$18"), ("GateSize", "$B$19"),
                ("NSkill", "$B$21"), ("NDst", "$B$22")]:
    wb.defined_names.add(DefinedName(nm, attr_text=f"'League Config'!{ref}"))

# =====================================================================
# 2. Manual Adjustments  (row-aligned with LIVE SOURCE)
# =====================================================================
ma = sheet2("Manual Adjustments",
            "Manual Injury / Role Adjustments (the only place you tweak players)",
            ["Pos", "Player", "Base Rating", "Injury Adj", "Role Adj", "Other Adj",
             "Total Adj", "News / Reason", "Last Updated", "Source"],
            [6, 22, 11, 9, 9, 9, 9, 55, 12, 30], tab_color="2E75B6")
for i, p in enumerate(players):
    r = DS + i
    ma.cell(r, 1).value = f"='LIVE SOURCE'!A{r}"
    ma.cell(r, 2).value = f"='LIVE SOURCE'!B{r}"
    ma.cell(r, 3).value = f"='LIVE SOURCE'!D{r}"
    ma.cell(r, 7).value = f"=SUM(D{r}:F{r})"
    ma.cell(r, 9, "2026-08-11")
# carry the live adjustments
ADJ = {
    "Makai Lemon": (-3, "Camp hamstring issue / missed practice time; temporary downgrade."),
    "Ricky Pearsall": (-60, "Season-ending PCL surgery announced 8/1/2026; out for the year (NFL.com)."),
}
for i, p in enumerate(players):
    if p["player"] in ADJ:
        r = DS + i
        adj, note = ADJ[p["player"]]
        ma.cell(r, 4, adj)
        ma.cell(r, 8, note)
edit_mark(ma, ["D", "E", "F", "H", "I", "J"])
numfmt(ma, ["C"], "0.0")

# =====================================================================
# 3. LIVE SOURCE (canonical table, static inputs)
# =====================================================================
ls = sheet2("LIVE SOURCE",
            "LIVE SOURCE: the one canonical table. one canonical table. Every other tab reads from here.",
            ["Pos", "Player", "Team", "Base Rating", "Market ADP", "Confidence",
             "Model Path", "2026 Expectation", "Why", "Main Risk", "Source"],
            [6, 22, 6, 11, 10, 10, 22, 50, 60, 50, 40], tab_color="ED7D31")
for i, p in enumerate(players):
    r = DS + i
    ls.cell(r, 1, p["pos"])
    ls.cell(r, 2, p["player"])
    ls.cell(r, 3, p.get("team") or "")
    ls.cell(r, 4, round(p["base"], 4))
    ls.cell(r, 5, float(p["adp"]))
    ls.cell(r, 6, p["confidence"])
    ls.cell(r, 7, p["model_path"])
    ls.cell(r, 8, p["expectation"])
    ls.cell(r, 9, p["why"])
    ls.cell(r, 10, p["risk"])
    ls.cell(r, 11, p["source"])
edit_mark(ls, ["D", "E", "F"])
numfmt(ls, ["D", "E"], "0.0")
dv_conf = DataValidation(type="list", formula1='"A,B,C"', allow_blank=True)
ls.add_data_validation(dv_conf)
dv_conf.add(f"F{DS}:F{DE_END}")

# =====================================================================
# 4. Draft Engine (all math lives here; row-aligned)
# =====================================================================
de = sheet2("Draft Engine",
            "Draft Engine: live math. Mark players in the Status column on draft day.",
            ["Pos", "Player", "Base Rating", "Manual Adj", "Adjusted Rating", "Pos Rank",
             "Proj Points", "Repl Rank", "Repl Points", "VORP", "VORP Score", "Scarcity",
             "Penalty", "Draft Score", "Skill Score", "Skill Rank", "Overall Rank",
             "Market ADP", "Draft Edge", "Confidence", "Floor", "Median", "Ceiling",
             "Model Path", "Status", "Avail Rank"],
            [6, 22, 10, 9, 11, 8, 10, 9, 10, 8, 10, 9, 8, 11, 8, 8, 10, 10, 9, 10, 8, 8, 8, 22, 11, 9],
            tab_color="70AD47")
PT = f"$A${DS}:$A${DE_END}"   # pos column range
for i, p in enumerate(players):
    r = DS + i
    de.cell(r, 1).value = f"='LIVE SOURCE'!A{r}"
    de.cell(r, 2).value = f"='LIVE SOURCE'!B{r}"
    de.cell(r, 3).value = f"='LIVE SOURCE'!D{r}"
    de.cell(r, 4).value = f"='Manual Adjustments'!G{r}"
    de.cell(r, 5).value = f"=MAX(40,MIN(100,C{r}+D{r}))"
    de.cell(r, 6).value = (f'=COUNTIFS({PT},A{r},$E${DS}:$E${DE_END},">"&E{r})'
                           f'+COUNTIFS($A${DS}:A{r},A{r},$E${DS}:E{r},E{r})')
    de.cell(r, 7).value = (f"=ROUND(INDEX('League Config'!$K$4:$K$9,MATCH(A{r},'League Config'!$E$4:$E$9,0))*E{r}"
                           f"+INDEX('League Config'!$L$4:$L$9,MATCH(A{r},'League Config'!$E$4:$E$9,0)),1)")
    de.cell(r, 8).value = f"=INDEX('League Config'!$H$4:$H$9,MATCH(A{r},'League Config'!$E$4:$E$9,0))"
    de.cell(r, 9).value = f"=INDEX('League Config'!$I$4:$I$9,MATCH(A{r},'League Config'!$E$4:$E$9,0))"
    de.cell(r, 10).value = f"=ROUND(G{r}-I{r},1)"
    de.cell(r, 11).value = f"=MAX(0,MIN(100,50+J{r}*0.6))"
    de.cell(r, 12).value = (f"=MIN(100,MAX(0,(1-(F{r}-1)/(H{r}*1.5))*100"
                            f"*INDEX('League Config'!$J$4:$J$9,MATCH(A{r},'League Config'!$E$4:$E$9,0))))")
    de.cell(r, 13).value = (f'=IF(A{r}="K",\'League Config\'!$B$14,IF(A{r}="DST",\'League Config\'!$B$15,'
                            f'IF(A{r}="QB",\'League Config\'!$B$16,0)))')
    de.cell(r, 14).value = f"=MIN(100,MAX(0,0.55*E{r}+0.3*K{r}+0.15*L{r}-M{r}))"
    de.cell(r, 15).value = f'=IF(OR(A{r}="K",A{r}="DST"),"",N{r})'
    de.cell(r, 16).value = (f'=IF(O{r}="","",COUNTIF($O${DS}:$O${DE_END},">"&O{r})'
                            f'+COUNTIF($O${DS}:O{r},O{r}))')
    de.cell(r, 17).value = (f'=IF(A{r}="DST",IF(F{r}<=GateSize,DstStart-1+F{r},NSkill+2*GateSize+F{r}-GateSize),'
                            f'IF(A{r}="K",IF(F{r}<=GateSize,KStart-1+F{r},NSkill+GateSize+NDst+F{r}-GateSize),'
                            f'IF(P{r}<=DstStart-1,P{r},P{r}+2*GateSize)))')
    de.cell(r, 18).value = f"='LIVE SOURCE'!E{r}"
    de.cell(r, 19).value = f"=R{r}-Q{r}"
    de.cell(r, 20).value = f"='LIVE SOURCE'!F{r}"
    de.cell(r, 21).value = f'=MAX(40,E{r}-IF(T{r}="A",6,IF(T{r}="B",9,12)))'
    de.cell(r, 22).value = f"=E{r}"
    de.cell(r, 23).value = f'=MIN(100,E{r}+IF(T{r}="A",6,IF(T{r}="B",9,12)))'
    de.cell(r, 24).value = f"='LIVE SOURCE'!G{r}"
    # Status is edited on the Draft Board (rank-ordered); board row for rank Q is INDEX position Q
    de.cell(r, 25).value = (f'=IF(INDEX(\'Draft Board\'!$J${DS}:$J${DE_END},Q{r})="","Available",'
                            f'INDEX(\'Draft Board\'!$J${DS}:$J${DE_END},Q{r}))')
    de.cell(r, 26).value = (f'=IF(Y{r}<>"Available","",1+COUNTIFS($Y${DS}:$Y${DE_END},"Available",'
                            f'$Q${DS}:$Q${DE_END},"<"&Q{r}))')
numfmt(de, ["C", "D", "E", "G", "I", "J", "K", "L", "N", "O", "R", "U", "V", "W"], "0.0")
numfmt(de, ["S"], "0.0")
for col in ("O", "P"):
    for r in range(DS, DE_END + 1):
        de[f"{col}{r}"].font = HELPER_FONT
de.conditional_formatting.add(
    f"S{DS}:S{DE_END}",
    CellIsRule(operator="greaterThan", formula=["10"], fill=PatternFill("solid", fgColor=GREEN)))
de.conditional_formatting.add(
    f"S{DS}:S{DE_END}",
    CellIsRule(operator="lessThan", formula=["-10"], fill=PatternFill("solid", fgColor=RED)))

DEQ = f"'Draft Engine'!$Q${DS}:$Q${DE_END}"
DEF_ = f"'Draft Engine'!$F${DS}:$F${DE_END}"
DEA = f"'Draft Engine'!$A${DS}:$A${DE_END}"

def de_col(col):
    return f"'Draft Engine'!${col}${DS}:${col}${DE_END}"

def ls_col(col):
    return f"'LIVE SOURCE'!${col}${DS}:${col}${DE_END}"

# =====================================================================
# Rank views: FINAL Master, Top 200, Player Summaries
# =====================================================================
def rank_view(name, title, count, cols, widths, tab_color):
    """cols: list of (header, formula_template) where template may use {h}=helper cell, {r}=row."""
    ws = sheet2(name, title, [c[0] for c in cols] + ["Src"], widths + [6], tab_color)
    hcol = get_column_letter(len(cols) + 1)
    for k in range(1, count + 1):
        r = DS + k - 1
        ws[f"{hcol}{r}"] = f"=MATCH($A{r},{DEQ},0)"
        ws[f"{hcol}{r}"].font = HELPER_FONT
        for c, (_h, tmpl) in enumerate(cols, 1):
            ws.cell(r, c).value = tmpl.format(r=r, h=f"${hcol}{r}", k=k)
    return ws

fm_cols = [
    ("Overall", "={k}"),
    ("Pos", "=INDEX(" + de_col("A") + ",{h})"),
    ("Pos Rank", "=INDEX(" + de_col("F") + ",{h})"),
    ("Player / Defense", "=INDEX(" + de_col("B") + ",{h})"),
    ("Adj Rating", "=INDEX(" + de_col("E") + ",{h})"),
    ("Tier", TIER_F.format("$E{r}")),
    ("Proj Points", "=INDEX(" + de_col("G") + ",{h})"),
    ("VORP", "=INDEX(" + de_col("J") + ",{h})"),
    ("Draft Score", "=INDEX(" + de_col("N") + ",{h})"),
    ("Market ADP", "=INDEX(" + de_col("R") + ",{h})"),
    ("Draft Edge", "=INDEX(" + de_col("S") + ",{h})"),
    ("Confidence", "=INDEX(" + de_col("T") + ",{h})"),
    ("Model Path", "=INDEX(" + de_col("X") + ",{h})"),
    ("2026 Expectation", "=INDEX(" + ls_col("H") + ",{h})"),
    ("Main Risk", "=INDEX(" + ls_col("J") + ",{h})"),
]
fm = rank_view("FINAL Master", "2026 FINAL Master: every player, live-ranked, K/DST gated to the final rounds.",
               N, fm_cols, [8, 6, 8, 22, 10, 9, 10, 8, 11, 10, 9, 10, 22, 50, 50], "FFC000")
numfmt(fm, ["E", "G", "H", "I", "J", "K"], "0.0", DS, DE_END)

t200_cols = [
    ("Overall", "={k}"),
    ("Pos", "=INDEX(" + de_col("A") + ",{h})"),
    ("Pos Rank", "=INDEX(" + de_col("F") + ",{h})"),
    ("Player", "=INDEX(" + de_col("B") + ",{h})"),
    ("Draft Score", "=INDEX(" + de_col("N") + ",{h})"),
    ("Adj Rating", "=INDEX(" + de_col("E") + ",{h})"),
    ("Proj Points", "=INDEX(" + de_col("G") + ",{h})"),
    ("VORP", "=INDEX(" + de_col("J") + ",{h})"),
    ("Scarcity", "=INDEX(" + de_col("L") + ",{h})"),
    ("Market ADP", "=INDEX(" + de_col("R") + ",{h})"),
    ("Draft Edge", "=INDEX(" + de_col("S") + ",{h})"),
    ("Floor", "=INDEX(" + de_col("U") + ",{h})"),
    ("Ceiling", "=INDEX(" + de_col("W") + ",{h})"),
    ("Confidence", "=INDEX(" + de_col("T") + ",{h})"),
]
t200 = rank_view("Top 200", "2026 Overall Top 200: pure formula view, updates with every adjustment.",
                 200, t200_cols, [8, 6, 8, 22, 11, 10, 10, 8, 9, 10, 9, 8, 8, 10], "FFC000")
numfmt(t200, ["E", "F", "G", "H", "I", "J", "K", "L", "M"], "0.0", DS, DS + 199)

# =====================================================================
# Draft Board: full pool in overall order, mark picks right here
# =====================================================================
db_ws = sheet2("Draft Board",
               "Draft Board: go in order, mark every pick in the Pick column. Marked rows cross out.",
               ["Overall", "Pos", "Pos Rank", "Player / Defense", "Adj Rating", "Tier",
                "Draft Score", "Market ADP", "Draft Edge", "Pick", "Avail Rank",
                "2026 Expectation", "Src"],
               [8, 6, 8, 22, 10, 9, 11, 10, 9, 12, 9, 70, 6], tab_color="C00000")
db_ws["N1"] = "Freeze adjustments once the draft starts: picks attach to board slots, so do not edit Manual Adjustments mid-draft."
db_ws["N1"].font = SUB_FONT
for k in range(1, N + 1):
    r = DS + k - 1
    h = f"$M{r}"
    db_ws[f"M{r}"] = f"=MATCH($A{r},{DEQ},0)"
    db_ws[f"M{r}"].font = HELPER_FONT
    db_ws.cell(r, 1, k)
    db_ws.cell(r, 2).value = f"=INDEX({de_col('A')},{h})"
    db_ws.cell(r, 3).value = f"=INDEX({de_col('F')},{h})"
    db_ws.cell(r, 4).value = f"=INDEX({de_col('B')},{h})"
    db_ws.cell(r, 5).value = f"=INDEX({de_col('E')},{h})"
    db_ws.cell(r, 6).value = TIER_F.format(f"$E{r}")
    db_ws.cell(r, 7).value = f"=INDEX({de_col('N')},{h})"
    db_ws.cell(r, 8).value = f"=INDEX({de_col('R')},{h})"
    db_ws.cell(r, 9).value = f"=INDEX({de_col('S')},{h})"
    db_ws.cell(r, 11).value = f"=INDEX({de_col('Z')},{h})"
    db_ws.cell(r, 12).value = f"=INDEX({ls_col('H')},{h})"
numfmt(db_ws, ["E", "G", "H", "I"], "0.0")
edit_mark(db_ws, ["J"])
dv_pick = DataValidation(type="list", formula1='"Drafted,My Pick"', allow_blank=True)
db_ws.add_data_validation(dv_pick)
dv_pick.add(f"J{DS}:J{DE_END}")
db_ws.conditional_formatting.add(
    f"A{DS}:L{DE_END}",
    FormulaRule(formula=[f'$J{DS}="My Pick"'], fill=PatternFill("solid", fgColor=GREEN),
                stopIfTrue=True))
db_ws.conditional_formatting.add(
    f"A{DS}:L{DE_END}",
    FormulaRule(formula=[f'$J{DS}<>""'], font=Font(strike=True, color=GRAY)))

ps_cols = [
    ("Overall", "={k}"),
    ("Pos", "=INDEX(" + de_col("A") + ",{h})"),
    ("Pos Rank", "=INDEX(" + de_col("F") + ",{h})"),
    ("Player / Defense", "=INDEX(" + de_col("B") + ",{h})"),
    ("Adj Rating", "=INDEX(" + de_col("E") + ",{h})"),
    ("2026 Expectation", "=INDEX(" + ls_col("H") + ",{h})"),
    ("Why We Rank Him Here", "=INDEX(" + ls_col("I") + ",{h})"),
    ("Main Risk / What Changes It", "=INDEX(" + ls_col("J") + ",{h})"),
    ("Market ADP", "=INDEX(" + de_col("R") + ",{h})"),
    ("Draft Edge", "=INDEX(" + de_col("S") + ",{h})"),
    ("Confidence", "=INDEX(" + de_col("T") + ",{h})"),
    ("Model Path", "=INDEX(" + de_col("X") + ",{h})"),
]
ps = rank_view("Player Summaries", "2026 Expectations: what we expect, why, and the risk. Ranks are live.",
               N, ps_cols, [8, 6, 8, 22, 10, 55, 65, 55, 10, 9, 10, 22], "FFC000")
numfmt(ps, ["E"], "0.0", DS, DE_END)

# =====================================================================
# Positional views: FINAL QB/RB/WR/TE, K, DST
# =====================================================================
def pos_view(name, title, pos, extra_prose=False, team=False):
    r1, r2, n = blocks[pos]
    def db(col):
        return f"'Draft Engine'!${col}${r1}:${col}${r2}"
    def lb(col):
        return f"'LIVE SOURCE'!${col}${r1}:${col}${r2}"
    cols = [("Pos Rank", "={k}")]
    if True:
        cols.append(("Player" if pos not in ("DST",) else "Defense", "=INDEX(" + db("B") + ",{h})"))
    if team:
        cols.append(("Team", "=INDEX(" + lb("C") + ",{h})"))
    cols += [
        ("Adj Rating", "=INDEX(" + db("E") + ",{h})"),
        ("Tier", TIER_F.format("$" + ("C" if not team else "D") + "{r}")),
        ("Proj Points", "=INDEX(" + db("G") + ",{h})"),
        ("VORP", "=INDEX(" + db("J") + ",{h})"),
        ("Draft Score", "=INDEX(" + db("N") + ",{h})"),
        ("Overall Rank", "=INDEX(" + db("Q") + ",{h})"),
        ("Market ADP", "=INDEX(" + db("R") + ",{h})"),
        ("Draft Edge", "=INDEX(" + db("S") + ",{h})"),
        ("Confidence", "=INDEX(" + db("T") + ",{h})"),
        ("2026 Expectation", "=INDEX(" + lb("H") + ",{h})"),
        ("Main Risk", "=INDEX(" + lb("J") + ",{h})"),
    ]
    widths = [8, 22] + ([6] if team else []) + [10, 9, 10, 8, 11, 11, 10, 9, 10, 55, 50]
    ws = sheet2(name, title, [c[0] for c in cols] + ["Src"], widths + [6], "A9D18E")
    hcol = get_column_letter(len(cols) + 1)
    for k in range(1, n + 1):
        r = DS + k - 1
        ws[f"{hcol}{r}"] = f"=MATCH($A{r},{db('F')},0)"
        ws[f"{hcol}{r}"].font = HELPER_FONT
        for c, (_h, tmpl) in enumerate(cols, 1):
            ws.cell(r, c).value = tmpl.format(r=r, h=f"${hcol}{r}", k=k)
    rating_col = "C" if not team else "D"
    numfmt(ws, [rating_col], "0.0", DS, DS + n - 1)
    return ws

pos_view("FINAL QB", "2026 QB: final rankings, live.", "QB")
pos_view("FINAL RB", "2026 RB: final rankings, live.", "RB")
pos_view("FINAL WR", "2026 WR: final rankings, live.", "WR")
pos_view("FINAL TE", "2026 TE: final rankings, live.", "TE")
pos_view("K", "2026 Kickers: final-round picks only. Top 10 gated to overall 141-150.", "K", team=True)
pos_view("DST", "2026 DST: final-round picks only. Top 10 gated to overall 131-140.", "DST", team=True)

# =====================================================================
# Draft Room
# =====================================================================
dr = wb.create_sheet("Draft Room")
dr.sheet_properties.tabColor = "70AD47"
dr["A1"] = "Draft Room: live board for draft day"
dr["A1"].font = TITLE_FONT
dr["A2"] = "Mark picks in Draft Engine Status column. This board updates itself."
dr["A2"].font = SUB_FONT
for c, h in enumerate(["Draft Input", "Value"], 1):
    cell = dr.cell(4, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
dr["A5"] = "Current Pick"; dr["B5"] = 1; dr["B5"].fill = EDIT_FILL
dr["A6"] = "Teams"; dr["B6"] = "='League Config'!$B$4"
dr["A7"] = "Roster Size"; dr["B7"] = "=SUM('League Config'!$B$6:$B$13)"

for c, h in enumerate(["Signal", "Interpretation", "Action"], 4):
    cell = dr.cell(4, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
signals = [
    ("Draft Edge > +15", "Strong model value", "Prioritize if roster construction fits."),
    ("Draft Edge -10 to +15", "Fairly priced", "Take best roster fit."),
    ("Draft Edge < -10", "Market reaching", "Let someone else pay the premium."),
]
for i, row in enumerate(signals):
    for c, v in enumerate(row, 4):
        dr.cell(5 + i, c, v)

dr["A10"] = "Best Available (Top 10)"
dr["A10"].font = Font(bold=True, size=11, color=NAVY)
for c, h in enumerate(["Avail Rank", "Player", "Pos", "Draft Score", "Overall", "ADP", "Edge"], 1):
    cell = dr.cell(11, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
DEZ = f"'Draft Engine'!$Z${DS}:$Z${DE_END}"
for k in range(1, 11):
    r = 11 + k
    dr.cell(r, 1, k)
    m = f"MATCH($A{r},{DEZ},0)"
    dr.cell(r, 2).value = f'=IFERROR(INDEX({de_col("B")},{m}),"")'
    dr.cell(r, 3).value = f'=IFERROR(INDEX({de_col("A")},{m}),"")'
    dr.cell(r, 4).value = f'=IFERROR(ROUND(INDEX({de_col("N")},{m}),1),"")'
    dr.cell(r, 5).value = f'=IFERROR(INDEX({de_col("Q")},{m}),"")'
    dr.cell(r, 6).value = f'=IFERROR(INDEX({de_col("R")},{m}),"")'
    dr.cell(r, 7).value = f'=IFERROR(INDEX({de_col("S")},{m}),"")'

dr["A24"] = "Best Available by Position"
dr["A24"].font = Font(bold=True, size=11, color=NAVY)
for c, h in enumerate(["Pos", "Player", "Overall Rank", "Draft Score"], 1):
    cell = dr.cell(25, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
for i, pos in enumerate(["QB", "RB", "WR", "TE", "K", "DST"]):
    r1, r2, _ = blocks[pos]
    r = 26 + i
    dr.cell(r, 1, pos)
    best = (f"_xlfn.AGGREGATE(15,6,'Draft Engine'!$Q${r1}:$Q${r2}/"
            f"('Draft Engine'!$Y${r1}:$Y${r2}=\"Available\"),1)")
    m = f"MATCH({best},{DEQ},0)"
    dr.cell(r, 2).value = f'=IFERROR(INDEX({de_col("B")},{m}),"None left")'
    dr.cell(r, 3).value = f'=IFERROR({best},"")'
    dr.cell(r, 4).value = f'=IFERROR(ROUND(INDEX({de_col("N")},{m}),1),"")'
dr["A34"] = "My Roster (marked My Pick on the Draft Board)"
dr["A34"].font = Font(bold=True, size=11, color=NAVY)
for c, h in enumerate(["Pos", "Count"], 1):
    cell = dr.cell(35, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL
for i, pos in enumerate(["QB", "RB", "WR", "TE", "K", "DST"]):
    r = 36 + i
    dr.cell(r, 1, pos)
    dr.cell(r, 2).value = f'=COUNTIFS({DEA},"{pos}",{de_col("Y")},"My Pick")'
dr.cell(42, 1, "Total")
dr.cell(42, 2).value = f'=COUNTIF({de_col("Y")},"My Pick")'
for col, w in zip("ABCDEFG", [14, 22, 13, 12, 26, 10, 8]):
    dr.column_dimensions[col].width = w

# =====================================================================
# QA Checks
# =====================================================================
qa = wb.create_sheet("QA Checks")
qa.sheet_properties.tabColor = "C00000"
qa["A1"] = "QA Checks: every number below must PASS before you trust the board"
qa["A1"].font = TITLE_FONT
for c, h in enumerate(["Check", "Expected", "Actual", "Status"], 1):
    cell = qa.cell(3, c); cell.value = h; cell.font = HDR_FONT; cell.fill = HDR_FILL

def gate(posrank, pos):
    return (f"=SUMPRODUCT(({DEA}=\"{pos}\")*({DEF_}={posrank})*{DEQ})")

fm_players = f"'FINAL Master'!$D${DS}:$D${DE_END}"
t2_players = f"'Top 200'!$D${DS}:$D${DS+199}"
err_ranges = [
    ("Draft Engine", f"'Draft Engine'!$A${DS}:$Z${DE_END}"),
    ("FINAL Master", f"'FINAL Master'!$A${DS}:$P${DE_END}"),
    ("Top 200", f"'Top 200'!$A${DS}:$O${DS+199}"),
    ("Player Summaries", f"'Player Summaries'!$A${DS}:$M${DE_END}"),
    ("League Config", "'League Config'!$F$4:$L$9"),
    ("Manual Adjustments", f"'Manual Adjustments'!$A${DS}:$J${DE_END}"),
    ("FINAL QB", f"'FINAL QB'!$A${DS}:$N${DS+blocks['QB'][2]-1}"),
    ("FINAL RB", f"'FINAL RB'!$A${DS}:$N${DS+blocks['RB'][2]-1}"),
    ("FINAL WR", f"'FINAL WR'!$A${DS}:$N${DS+blocks['WR'][2]-1}"),
    ("FINAL TE", f"'FINAL TE'!$A${DS}:$N${DS+blocks['TE'][2]-1}"),
    ("K", f"'K'!$A${DS}:$O${DS+blocks['K'][2]-1}"),
    ("DST", f"'DST'!$A${DS}:$O${DS+blocks['DST'][2]-1}"),
    ("Draft Room", "'Draft Room'!$A$5:$G$42"),
    ("Draft Board", f"'Draft Board'!$A${DS}:$M${DE_END}"),
]
err_sum = "+".join(f"SUMPRODUCT(--ISERROR({rng}))" for _n, rng in err_ranges)

checks = [
    ("Player count (LIVE SOURCE)", N, f"=COUNTA('LIVE SOURCE'!$B${DS}:$B${DE_END})"),
    ("Row alignment errors (LS vs Draft Engine)", 0,
     f"=SUMPRODUCT(--({ls_col('B')}<>{de_col('B')}))"),
    ("Row alignment errors (LS vs Manual Adj)", 0,
     f"=SUMPRODUCT(--({ls_col('B')}<>'Manual Adjustments'!$B${DS}:$B${DE_END}))"),
    ("Master mismatches (dupes + errors)", 0,
     f"=IFERROR({N}-SUMPRODUCT(1/COUNTIF({fm_players},{fm_players})),999)"
     f"+SUMPRODUCT(--ISERROR('FINAL Master'!$A${DS}:$P${DE_END}))"),
    ("Top 200 mismatches (dupes + errors)", 0,
     f"=IFERROR(200-SUMPRODUCT(1/COUNTIF({t2_players},{t2_players})),999)"
     f"+SUMPRODUCT(--ISERROR('Top 200'!$A${DS}:$O${DS+199}))"),
    ("Positional-rank conflicts", 0,
     f"=SUMPRODUCT(--(COUNTIFS({DEA},{DEA},{DEF_},{DEF_})>1))"),
    ("Overall-rank conflicts", 0,
     f"=SUMPRODUCT(--(COUNTIF({DEQ},{DEQ})>1))"),
    ("DST1 overall rank", 131, gate(1, "DST")),
    ("DST10 overall rank", 140, gate(10, "DST")),
    ("K1 overall rank", 141, gate(1, "K")),
    ("K10 overall rank", 150, gate(10, "K")),
    ("VORP identity errors (VORP = Pts - Repl Pts)", 0,
     f"=SUMPRODUCT(--(ABS({de_col('J')}-({de_col('G')}-{de_col('I')}))>0.06))"),
    ("Formula errors (all sheets)", 0, "=" + err_sum),
]
r = 4
for name, exp, actual in checks:
    qa.cell(r, 1, name)
    qa.cell(r, 2, exp)
    qa.cell(r, 3).value = actual
    qa.cell(r, 4).value = f'=IF($C{r}=$B{r},"PASS","FAIL")'
    r += 1
last_check = r - 1
qa.cell(r + 1, 1, "OVERALL")
qa.cell(r + 1, 1).font = Font(bold=True, size=12)
qa.cell(r + 1, 4).value = (f'=IF(COUNTIF($D$4:$D${last_check},"FAIL")=0,"ALL CHECKS PASS",'
                           f'COUNTIF($D$4:$D${last_check},"FAIL")&" CHECKS FAILING")')
qa.cell(r + 1, 4).font = Font(bold=True, size=12)
qa.conditional_formatting.add(
    f"D4:D{r + 1}", CellIsRule(operator="equal", formula=['"PASS"'],
                               fill=PatternFill("solid", fgColor=GREEN)))
qa.conditional_formatting.add(
    f"D4:D{r + 1}", CellIsRule(operator="notEqual", formula=['"PASS"'],
                               fill=PatternFill("solid", fgColor=RED)))
qa.conditional_formatting.add(
    f"D{r + 1}", CellIsRule(operator="equal", formula=['"ALL CHECKS PASS"'],
                            fill=PatternFill("solid", fgColor=GREEN)))
for col, w in zip("ABCD", [44, 10, 12, 20]):
    qa.column_dimensions[col].width = w

# per-sheet error detail
qa.cell(r + 3, 1, "Formula error detail by sheet")
qa.cell(r + 3, 1).font = Font(bold=True, size=11, color=NAVY)
rr = r + 4
for nm, rng in err_ranges:
    qa.cell(rr, 1, nm)
    qa.cell(rr, 3).value = f"=SUMPRODUCT(--ISERROR({rng}))"
    rr += 1

# =====================================================================
# tab order per Derek's spec
# =====================================================================
order = ["Draft Board", "League Config", "Manual Adjustments", "LIVE SOURCE", "FINAL Master",
         "Top 200", "FINAL QB", "FINAL RB", "FINAL WR", "FINAL TE", "K", "DST",
         "Draft Engine", "Draft Room", "Player Summaries", "QA Checks"]
wb._sheets = [wb[n] for n in order]
wb.active = wb["Draft Board"]

wb.save(OUT)
print("SAVED", OUT)
print("Blocks:", blocks)

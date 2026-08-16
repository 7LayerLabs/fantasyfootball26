"""Inspect available NFL data sources."""
import nfl_data_py as nfl

# Check what functions are available
print("Available nfl_data_py functions:")
funcs = [f for f in dir(nfl) if not f.startswith('_') and callable(getattr(nfl, f))]
for f in funcs:
    print(f"  {f}")

# Try snap counts
print("\nTrying snap counts...")
try:
    snaps = nfl.import_snap_counts([2024])
    print("Snap counts columns:", snaps.columns.tolist())
    print("Snap counts shape:", snaps.shape)
    print(snaps.head())
except Exception as e:
    print(f"Error: {e}")

# Try weekly rosters
print("\nTrying weekly rosters...")
try:
    rosters = nfl.import_weekly_rosters([2024])
    print("Weekly rosters columns:", rosters.columns.tolist()[:20])
except Exception as e:
    print(f"Error: {e}")

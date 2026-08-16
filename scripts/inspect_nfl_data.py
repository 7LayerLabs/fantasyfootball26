"""Inspect available NFL data columns."""
import nfl_data_py as nfl
import pandas as pd

print("Loading 2024 data...")
weekly = nfl.import_weekly_data([2024], downcast=False)
print("\nWeekly data columns:")
print(weekly.columns.tolist())
print("\nWeekly data shape:", weekly.shape)
print("\nFirst few rows:")
print(weekly.head())

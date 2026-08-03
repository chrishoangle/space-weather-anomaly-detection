"""Small smoke test for the NOAA data loader.

Run from the project root with: ``python scripts/fetch_noaa_data.py``.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import load_kp_index, load_solar_wind_plasma


if __name__ == "__main__":
    print("Solar wind plasma:")
    print(load_solar_wind_plasma().head())
    print("\nPlanetary Kp index:")
    print(load_kp_index().head())

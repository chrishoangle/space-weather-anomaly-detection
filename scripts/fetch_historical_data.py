"""Fetch and summarize the March 2015 St. Patrick's Day geomagnetic storm.

Run from the project root with: ``python scripts/fetch_historical_data.py``.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import fetch_omniweb_historical

if __name__ == "__main__":
    storm_data = fetch_omniweb_historical(
        datetime(2015, 3, 15, tzinfo=UTC),
        datetime(2015, 3, 20, tzinfo=UTC),
    )
    peak_time = storm_data["Kp"].idxmax()
    print(f"Records fetched: {len(storm_data)}")
    print(
        f"Peak Kp: {storm_data.loc[peak_time, 'Kp']:.1f} "
        f"(OMNI's Kp 8- bin) at {peak_time.isoformat()}"
    )
    print("\nSolar-wind velocity (km/s):")
    print(storm_data["speed"].describe().to_string())
    print("\nSolar-wind proton density (cm^-3):")
    print(storm_data["density"].describe().to_string())

#!/usr/bin/env python3
"""Command-line historical dataset collection."""
import argparse
from agents.historical_data_agent import collect_historical_data
from config import HISTORICAL_TIMEFRAME


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", default=HISTORICAL_TIMEFRAME)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--delay", type=float, default=8.0)
    args = parser.parse_args()
    path, metadata = collect_historical_data(
        timeframe=args.timeframe, refresh=args.refresh, delay_seconds=args.delay
    )
    print(f"Historical dataset saved: {path}")
    print(f"Rows: {metadata['rows']} | Keywords: {metadata['keywords_collected']}")
    print(f"Dates: {metadata['date_min']} to {metadata['date_max']}")


if __name__ == "__main__":
    from cli_v4 import main as configured_main
    configured_main("collect")

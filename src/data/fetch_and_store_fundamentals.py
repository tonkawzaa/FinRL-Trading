#!/usr/bin/env python3
"""Fetch fundamental data for a stock universe and store to local database.

Features:
  - DB cache:  Skips tickers already present in the database for the requested date range.
  - Batching:  Processes tickers in batches (default 50) to stay within FMP's 250 calls/day free-plan limit.
  - Resume:    Saves progress to a JSON file; re-running the script continues where it left off.
  - Rate-limit aware: Catches FMP 402/429 and stops the current run, saving progress for resumption.

Usage:
  python3 src/data/fetch_and_store_fundamentals.py --universe nasdaq100
  python3 src/data/fetch_and_store_fundamentals.py --universe sp500 --batch-size 40
  python3 src/data/fetch_and_store_fundamentals.py --universe nasdaq100 --force-refresh
"""

import argparse
import json
import os
import sys
import time

# Allow running as standalone script: python3 src/data/fetch_and_store_fundamentals.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, "src"))

import pandas as pd
from data.data_fetcher import (
    FMPRateLimitError,
    fetch_fundamental_data, fetch_sp500_tickers, fetch_nasdaq100_tickers,
    get_all_historical_sp500_tickers,
)
from data.data_store import get_data_store

PROGRESS_DIR = os.path.join(project_root, "data", ".progress")


def _progress_path(universe: str) -> str:
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    return os.path.join(PROGRESS_DIR, f"fund_fetch_{universe}.json")


def _load_progress(universe: str) -> dict:
    path = _progress_path(universe)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_progress(universe: str, data: dict):
    path = _progress_path(universe)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _clear_progress(universe: str):
    path = _progress_path(universe)
    if os.path.exists(path):
        os.remove(path)


def get_cached_tickers(store, start_date: str, end_date: str) -> set:
    """Return set of tickers that already have >= 4 quarters of data in DB."""
    try:
        df = store.get_fundamental_data(start_date=start_date, end_date=end_date)
        if df.empty:
            return set()
        # A ticker is 'cached' if it has at least 4 quarterly records in range
        counts = df.groupby("tic").size()
        return set(counts[counts >= 4].index)
    except Exception:
        return set()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch & store fundamentals (with batching + resumable progress)"
    )
    parser.add_argument("--universe", default="sp500", choices=["sp500", "nasdaq100"],
                        help="Stock universe (default: sp500)")
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default="2026-04-01")
    parser.add_argument("--limit", type=int, default=10000, help="Universe cap")
    parser.add_argument("--preferred-source", default="FMP")
    parser.add_argument("--output-csv", default=None, help="Also save to CSV")
    parser.add_argument("--survivorship-free", action="store_true",
                        help="Use all historical SP500 tickers (not just current) to avoid survivorship bias")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Tickers per batch (default 50 ≈ 200 FMP calls; free plan allows 250/day)")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Ignore DB cache and re-fetch all tickers")
    parser.add_argument("--reset-progress", action="store_true",
                        help="Clear saved progress and start from scratch")
    args = parser.parse_args()

    universe_key = f"{args.universe}{'_surv' if args.survivorship_free else ''}"

    # Handle reset
    if args.reset_progress:
        _clear_progress(universe_key)
        print("Progress reset.")

    # 1. Get tickers
    if args.survivorship_free:
        print("Survivorship-free mode: collecting ALL historical SP500 tickers ...")
        all_hist = get_all_historical_sp500_tickers(start_date=args.start_date)
        current = fetch_sp500_tickers(preferred_source=args.preferred_source)
        current_set = set(current["tickers"].tolist()) if current is not None else set()
        combined = sorted(all_hist | current_set)
        tickers_df = pd.DataFrame({"tickers": combined, "sectors": ""})
        print(f"Universe: {len(tickers_df)} tickers (historical: {len(all_hist)}, current: {len(current_set)})")
    else:
        print(f"Fetching {args.universe.upper()} universe ...")
        if args.universe == "nasdaq100":
            tickers_df = fetch_nasdaq100_tickers(preferred_source=args.preferred_source)
        else:
            tickers_df = fetch_sp500_tickers(preferred_source=args.preferred_source)

        if tickers_df is None or len(tickers_df) == 0:
            raise ValueError(f"Failed to fetch {args.universe} tickers")
        if args.limit > 0:
            tickers_df = tickers_df.head(args.limit)
        print(f"Universe: {len(tickers_df)} tickers")

    all_tickers = tickers_df["tickers"].tolist()

    # 2. Check DB cache — skip tickers already in DB
    store = get_data_store()
    if args.force_refresh:
        cached = set()
        print("Force-refresh: ignoring DB cache")
    else:
        cached = get_cached_tickers(store, args.start_date, args.end_date)
        if cached:
            print(f"DB cache: {len(cached)} tickers already have data — skipping them")

    # 3. Load progress — skip tickers completed in previous runs
    progress = _load_progress(universe_key)
    completed_tickers = set(progress.get("completed", []))
    if completed_tickers:
        print(f"Resume: {len(completed_tickers)} tickers completed in previous runs")

    # Determine which tickers still need fetching
    skip = cached | completed_tickers
    remaining = [t for t in all_tickers if t not in skip]
    print(f"Remaining tickers to fetch: {len(remaining)} / {len(all_tickers)}")

    if not remaining:
        print("\nAll tickers already fetched! Use --force-refresh to re-fetch.")
        # Still show summary from DB
        _show_summary(store, all_tickers, args)
        _clear_progress(universe_key)
        return

    # 4. Batch processing
    batch_size = args.batch_size
    total_batches = (len(remaining) - 1) // batch_size + 1
    total_saved = 0
    rate_limited = False

    print(f"\nProcessing {len(remaining)} tickers in {total_batches} batch(es) of {batch_size}")
    print(f"(Each ticker uses ~4 FMP API calls; free plan limit is 250/day)")
    print(f"{'='*60}")

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(remaining))
        batch = remaining[batch_start:batch_end]
        batch_num = batch_idx + 1

        estimated_calls = len(batch) * 4  # income, balance, cashflow, ratios
        print(f"\n--- Batch {batch_num}/{total_batches}: {len(batch)} tickers "
              f"({batch[0]}..{batch[-1]}) ~{estimated_calls} API calls ---")

        # Build DataFrame for this batch
        batch_rows = tickers_df[tickers_df["tickers"].isin(batch)]
        if batch_rows.empty:
            # Tickers not in original DataFrame (e.g., historical survivorship-free)
            batch_rows = pd.DataFrame({
                "tickers": batch,
                "sectors": [""] * len(batch),
            })

        try:
            df = fetch_fundamental_data(
                batch_rows,
                args.start_date, args.end_date,
                preferred_source=args.preferred_source,
            )

            if not df.empty:
                n = store.save_fundamental_data(df)
                total_saved += n
                print(f"  ✓ Fetched {len(df)} records, saved {n} to DB")
            else:
                print(f"  ⚠ No data returned for this batch")

            # Mark batch tickers as completed
            completed_tickers.update(batch)
            progress["completed"] = sorted(completed_tickers)
            progress["last_batch"] = batch_num
            progress["last_updated"] = pd.Timestamp.now().isoformat()
            _save_progress(universe_key, progress)

        except FMPRateLimitError as e:
            print(f"\n{'='*60}")
            print(f"  ✗ FMP rate limit hit ({e.status_code}) at ticker {e.ticker}")
            print(f"    Progress saved — re-run this script to continue from batch {batch_num}")
            print(f"    Completed so far: {len(completed_tickers)} / {len(all_tickers)} tickers")
            print(f"{'='*60}")
            rate_limited = True
            # Save progress before exiting
            progress["completed"] = sorted(completed_tickers)
            progress["last_batch"] = batch_num
            progress["rate_limited_at"] = pd.Timestamp.now().isoformat()
            _save_progress(universe_key, progress)
            break

        except Exception as e:
            print(f"  ✗ Batch error: {e}")
            # Save progress and continue to next batch
            progress["completed"] = sorted(completed_tickers)
            _save_progress(universe_key, progress)
            continue

        # Brief pause between batches to be polite to the API
        if batch_num < total_batches:
            print(f"  Pausing 2s before next batch ...")
            time.sleep(2)

    # 5. Summary
    print(f"\n{'='*60}")
    print(f"Run complete{'  (rate limited — re-run to continue)' if rate_limited else ''}")
    print(f"  Total saved this run: {total_saved} records")
    print(f"  Completed tickers:    {len(completed_tickers)} / {len(all_tickers)}")

    if len(completed_tickers) >= len(all_tickers):
        # All done — clear progress file
        _clear_progress(universe_key)
        print(f"  ✓ All tickers complete! Progress file cleared.")

    _show_summary(store, all_tickers, args)

    # 6. Optional CSV export
    if args.output_csv and not rate_limited:
        full_df = store.get_fundamental_data(
            tickers=all_tickers,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        if not full_df.empty:
            out = args.output_csv
            if not os.path.isabs(out):
                out = os.path.join(project_root, out)
            os.makedirs(os.path.dirname(out) if os.path.dirname(out) else ".", exist_ok=True)
            full_df.to_csv(out, index=False)
            print(f"  CSV saved to {out}")


def _show_summary(store, all_tickers, args):
    """Print summary of data in DB for the requested universe."""
    try:
        df = store.get_fundamental_data(
            tickers=all_tickers,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        if not df.empty:
            print(f"\nDB Summary:")
            print(f"  Tickers in DB: {df['tic'].nunique()} / {len(all_tickers)}")
            print(f"  Date range:    {df['datadate'].min()} ~ {df['datadate'].max()}")
            print(f"  Total records: {len(df)}")
        else:
            print(f"\nDB Summary: No data in DB for this universe/date range yet.")
    except Exception as e:
        print(f"\nDB Summary: Error reading — {e}")


if __name__ == "__main__":
    main()

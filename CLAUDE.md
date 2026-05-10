# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run via deploy script (preferred entry point)
./deploy.sh --strategy adaptive_rotation --mode backtest --start 2020-01-01 --end 2024-12-31
./deploy.sh --strategy adaptive_rotation --mode single --date 2024-12-31
./deploy.sh --strategy adaptive_rotation --mode paper --dry-run   # preview orders
./deploy.sh --strategy adaptive_rotation --mode paper             # execute

# Run strategy directly (bypasses deploy.sh data download)
python src/strategies/run_adaptive_rotation_strategy.py \
    --config src/strategies/AdaptiveRotationConf_v1.2.1.yaml \
    --backtest --start 2023-01-01 --end 2024-12-31

# ML stock selection
python3 src/strategies/ml_bucket_selection.py --universe sp500 --mixed-vintage

# Download fundamental data (resumable; respects FMP 250 calls/day limit)
python3 src/data/fetch_and_store_fundamentals.py --universe sp500

# Web dashboard
streamlit run src/web/app.py

# CLI entry point (dashboard | backtest | trade | data | config)
python src/main.py dashboard
```

## Architecture

**Weight-centric design:** Every strategy module outputs a portfolio weight vector `w_t`. This is the sole interface contract between strategy logic and downstream execution, making backtest and live execution interchangeable.

### Layer Overview

```
Data Layer  →  Strategy Layer  →  Backtest Layer  →  Execution Layer
src/data/      src/strategies/    src/backtest/       src/trading/
```

**Data Layer** (`src/data/`): Fetches from FMP (primary), Yahoo Finance (fallback on 402/429), and WRDS. All data cached in SQLite at `data/finrl_trading.db`. Point-in-time historical constituent lists prevent survivorship bias. `fetch_and_store_fundamentals.py` stores 50+ financial ratios with cross-day resumable progress at `data/.progress/fund_fetch_*.json`.

**Strategy Layer** (`src/strategies/`): All strategies implement `BaseStrategy.generate_weights()` returning `StrategyResult(weights: pd.DataFrame)`. Two main strategies:
1. **`adaptive_rotation/`** — Production strategy (v1.2.1). Regime-first 7-module pipeline (see below).
2. **`ml_bucket_selection.py`** — ML ensemble (7 models + stacking) that ranks S&P 500 stocks within 4 sector buckets using 33 fundamental features.

**Backtest Layer** (`src/backtest/backtest_engine.py`): Uses the `bt` library. Configurable via `BacktestConfig` (rebalance frequency, transaction costs, benchmarks). Returns Sharpe, Calmar, max drawdown, trades history.

**Execution Layer** (`src/trading/`): Alpaca API integration via `AlpacaManager` supporting multiple accounts. `deploy.sh` enforces paper-only execution (refuses live account orders).

**Configuration** (`src/config/settings.py`): Pydantic-based `FinRLSettings` loaded from `.env` + YAML. All sub-settings (Alpaca, FMP, Gemini, database, etc.) are type-safe. Use `from src.config.settings import get_config`.

## Adaptive Rotation Strategy — Core Pipeline

Located in `src/strategies/adaptive_rotation/`. The orchestrator is `adaptive_rotation_engine.py`. Per decision step:

```
Data → Regime → Group Strength → Intra-Group Ranking → Exception → Risk Mgmt → Portfolio → Audit
```

1. **`market_regime.py`** — Dual-layer detection: slow regime (weekly trend + drawdown + VIX → risk_on/neutral/risk_off) sets `group_cap` and `cash_floor`; fast regime (daily 3-day SPX drawdown ≤ −3%) triggers emergency de-risk. State must persist ≥2 weeks before switching.
2. **`group_strength.py`** — Ranks 3 asset groups (Growth Tech, Real Assets, Defensive) by information ratio vs QQQ.
3. **`intra_group_ranking.py`** — Residual momentum Z-scores (MAD-based, robust to outliers) within selected groups.
4. **`exception_framework.py`** — Momentum/Kindleberger persistence detection; prevents whipsaw by holding strong signals.
5. **`risk_manager.py`** — Trailing stop-loss (2%) and absolute stop-loss (20% from entry) with cooldown periods.
6. **`portfolio_builder.py`** — Assembles final weights respecting regime caps; includes cash allocation and fallback logic.
7. **`walk_forward.py`** — Backtest harness with weekly rebalancing + daily fast-regime monitoring.

Configuration: `src/strategies/AdaptiveRotationConf_v1.2.1.yaml`. Asset groups (symbols, max_assets) and all regime thresholds are YAML-controlled. Register new strategies in `deploy.sh`'s `STRATEGIES` variable.

## Key Abstractions

**`y_return` (ML training target):** Quarterly log return with a 2-month trade-date lag to model realistic report publication delay. Quarter-end 09-30 → trade date 12-01 of same year. Prevents look-ahead bias.

**ML feature set:** 33 features across valuation (P/E, P/B, EV/Sales), profitability (ROE, margins), cash flow (FCF/share), leverage, momentum (1Q/4Q returns), and one-hot sector dummies. Winsorized at 1st/99th percentile. Temporal (not random) train/test split.

**Audit trail:** `AdaptiveRotationEngine` produces a JSON-serializable audit log per decision for full explainability. Execution records saved to `weights_dir/signal_{date}.json` and `weights_dir/execution_{date}.json`.

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add APCA_API_KEY, APCA_API_SECRET, FMP_API_KEY, GEMINI_API_KEY
```

Key environment variables: `FMP_API_KEY` (fundamentals), `APCA_API_KEY` + `APCA_API_SECRET` (Alpaca paper trading), `GEMINI_API_KEY` (sentiment analysis, optional — can be disabled).

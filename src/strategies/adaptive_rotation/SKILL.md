# Adaptive Multi-Asset Rotation Strategy — SKILL.md

> **Version**: v1.2.1 · **Config**: `AdaptiveRotationConf_v1.2.1.yaml`

---

## 1. Overview

A **regime-aware, walk-forward-safe** systematic rotation strategy.
Macro market conditions constrain the risk budget and cash floors *before* any asset ranking occurs ("Regime-First" philosophy).

**Core pipeline per decision step:**

```
Data → Regime → Group Strength → Intra-Group Ranking → Exception → Risk Mgmt → Portfolio → Audit
```

---

## 2. Directory Structure

```
adaptive_rotation/
├── __init__.py                  # Exports AdaptiveRotationEngine (v1.2.1)
├── adaptive_rotation_engine.py  # Central orchestrator (660 lines)
├── config_loader.py             # Pydantic YAML validation (601 lines)
├── data_preprocessor.py         # CSV → weekly alignment (777 lines)
├── market_regime.py             # Slow + Fast regime detection (778 lines)
├── group_strength.py            # Inter-group IR ranking (480 lines)
├── intra_group_ranking.py       # Residual momentum Z-scores (550 lines)
├── exception_framework.py       # M/K persistence + Strong Signal (721 lines)
├── portfolio_builder.py         # Weight assembly + fallback (566 lines)
├── risk_manager.py              # Stop-loss + cooldown (557 lines)
├── walk_forward.py              # Backtest harness (556 lines)
├── SKILL.md                     # This document
└── utils/
    ├── __init__.py              # Re-exports all utils
    ├── robust_stats.py          # MAD, robust Z-score, IR (378 lines)
    └── calendar_utils.py        # NYSE trading calendar (486 lines)
```

---

## 3. Module Details & Parameters

### 3.1 `adaptive_rotation_engine.py` — Central Orchestrator

**Class `AdaptiveRotationEngine`**

| Constructor Arg | Type | Description |
|---|---|---|
| `config` | `str / Path / AdaptiveRotationConfig` | Config object or YAML path |
| `config_path` | `str / Path` | Alternative YAML path |
| `data_preprocessor` | `DataPreprocessor` | Optional; provides daily data for Fast Risk-Off |

**Main method — `engine.run()`**

| Arg | Type | Default | Description |
|---|---|---|---|
| `price_data` | `DataFrame / Dict[str, Series]` | — | Weekly close prices |
| `as_of_date` | `str / Timestamp` | — | Decision date |
| `current_positions` | `Dict[str, PositionState]` | `None` | For stop-loss tracking |
| `mode` | `str` | `"backtest"` | `"backtest"` or `"live"` |

**Returns:** `(PortfolioWeights, AuditLog)`

**6-step pipeline executed inside `run()`:**

1. `_detect_regime()` → `MarketRegimeResult`
2. `_analyze_group_strength()` → `GroupStrengthResult`
3. `_rank_assets_in_groups()` → `Dict[str, GroupRankingResult]`
4. `_detect_exceptions()` → `ExceptionDetectionResult`
5. `_check_stops()` → `RiskCheckResult`
6. `portfolio_builder.build()` → `PortfolioBuildResult`

**`AuditLog` dataclass** serializes every step to JSON for explainability.

---

### 3.2 `config_loader.py` — Pydantic Validation

Loads `AdaptiveRotationConf_v1.2.1.yaml` into `AdaptiveRotationConfig`.

**Key helper methods:**

| Method | Returns | Description |
|---|---|---|
| `get_all_symbols()` | `List[str]` | Unique symbols across all groups |
| `get_symbol_to_group_mapping()` | `Dict[str, str]` | symbol → group lookup |
| `get_required_symbols()` | `List[str]` | All symbols + `^GSPC`, `^VIX`, benchmark |
| `compute_config_hash()` | `str` | SHA-256 for state validation |
| `summary()` | `str` | Human-readable config summary |

**Standalone functions:**

```python
config = load_config("path/to/config.yaml")
is_valid, error = validate_config_file("path/to/config.yaml")
```

---

### 3.3 `data_preprocessor.py` — Data Ingestion

**Class `DataPreprocessor`**

| Method | Description |
|---|---|
| `load_and_prepare(data_dir, start_date, end_date)` | Load CSVs → weekly → align |
| `get_data_as_of(as_of_date, lookback_periods)` | Point-in-time weekly slice |
| `get_daily_data_as_of(as_of_date, symbols)` | Daily close for Fast Risk-Off |
| `get_weekly_returns(as_of_date, lookback_periods)` | Weekly pct_change |
| `has_sufficient_history(as_of_date, min_weeks)` | Validates ≥ N weeks |
| `get_available_date_range()` | `(start, end)` tuple |

**CSV format expected:** `{SYMBOL}_daily.csv` with columns `date, open, high, low, close, volume`.

**Weekly aggregation rules:** Open=first, High=max, Low=min, Close=last, Volume=sum.

**Alignment:** Forward-fill with `max_fill_gaps=2`.

---

### 3.4 `market_regime.py` — Dual-Layer Regime Detection

#### Slow Regime Gate (weekly, structural)

Three boolean signals scored 0–3:

| Signal | Condition | Score |
|---|---|---|
| `trend_deterioration` | SPX < 26-week MA | +1 |
| `drawdown_stress` | 13-week drawdown > 10% | +1 |
| `volatility_stress` | VIX Z-score > 3.0 (3-year lookback) | +1 |

**State mapping (from YAML `mapping` section):**

| Score | State | `group_cap` | `cash_floor` |
|---|---|---|---|
| 0 | `risk_on` | 1.0 | 0.0 |
| 1 | `neutral` | 0.7 | 0.1 |
| 2–3 | `risk_off` | 0.5 | 0.3 |

**Persistence filter:** State must persist ≥ 2 consecutive weeks before switching.

#### Fast Risk-Off Overlay (daily, emergency)

| Trigger | Condition |
|---|---|
| `price_shock` | 3-day SPX drawdown ≤ −3% |
| `volatility_shock` | VIX Z ≥ 3.0 **AND** ΔVIX Z ≥ 3.5 |

When active → `group_cap=0.3`, `cash_floor=0.5`, duration **10 days**, stop-loss multiplier **0.7×**.

---

### 3.5 `group_strength.py` — Inter-Group Ranking

**YAML parameters:**

```yaml
group_strength:
  metric: risk_adjusted_return   # "risk_adjusted_return" | "return" | "sharpe"
  lookback_weeks: 12
  trend_filter: true             # Only activate groups with positive excess return
```

**Process:**
1. Compute equal-weighted group returns from constituent prices
2. Compute excess returns vs benchmark (QQQ)
3. Calculate robust Information Ratio (MAD-based) via `compute_information_ratio()`
4. Rank groups by IR descending
5. `trend_filter=true` → only groups with excess_return > 0 qualify
6. Select top `max_active_groups` (default 2)

---

### 3.6 `intra_group_ranking.py` — Asset Selection

**Concept:** Residual Momentum = Asset Return − Group Return, normalized via robust Z-score.

| Parameter | Default | Description |
|---|---|---|
| `lookback_weeks` | 12 | Z-score rolling window |
| `robust` | `true` | Use MAD instead of std |
| `top_n_per_group` | 3 | Assets selected per group |
| `zscore_window` | 12 | Fixed window for Z-score |
| `max_zscore` | 20.0 | Clip extreme Z values |
| `min_mad_threshold` | 1e-6 | Prevent division by ≈0 |

**Data validity:** Requires ≥ 80% of lookback periods to be non-NaN.

---

### 3.7 `exception_framework.py` — Outlier Detection

Two qualification paths (OR logic):

**Rule 1 — M/K Persistence:**

| Param | YAML Key | Default | Description |
|---|---|---|---|
| Z threshold | `exception.z_threshold` | 2.5 | Per-week trigger threshold |
| K (window) | `exception.lookback_weeks` | 4 | Rolling window |
| M (count) | `exception.min_trigger_count` | 2 | Required triggers |

**Rule 2 — Strong Signal (single trigger):**

| Param | YAML Key | Default | Description |
|---|---|---|---|
| Enabled | `strong_signal.enabled` | `true` | — |
| Z threshold | `strong_signal.z_threshold` | 3.5 | Higher bar for single shot |
| Return multiplier | `strong_signal.return_multiplier` | 1.5 | 12w return > 1.5× QQQ |
| Lookback | `strong_signal.return_lookback_weeks` | 12 | — |
| Positive only | `strong_signal.require_positive_return` | `true` | — |

**Re-entry cooldown:** 6 weeks, with 1.5× stricter threshold.

---

### 3.8 `portfolio_builder.py` — Weight Assembly

**Process:**

1. `calculate_risk_budget()` → derives total equity allocation from regime
2. `allocate_group_budgets()` → equal split across active groups
3. `calculate_asset_weights_in_group()` → equal weight per selected asset
4. `apply_exception_multiplier()` → 1.5× for exception assets
5. `normalize_weights()` → cap total ≤ 1.0
6. Cash = residual (1.0 − invested)

**Fallback portfolio** (`portfolio.fallback`): When no groups qualify → equal-weight into `[SPY, QQQ, IAU, XLU, XLV]`.

| YAML Key | Default | Description |
|---|---|---|
| `max_active_groups` | 2 | — |
| `allow_exception` | `true` | — |
| `exception_weight_multiplier` | 1.5 | — |
| `weighting.scheme` | `equal` | Only `equal` implemented |
| `fallback.enabled` | `true` | — |

---

### 3.9 `risk_manager.py` — Stop-Loss & Cooldown

**`RiskManager` class:**

| Param | YAML Key | Default |
|---|---|---|
| Absolute threshold | `stop_loss.absolute.threshold` | −5% |
| Trailing threshold | `stop_loss.trailing.threshold` | −10% |
| Cooldown after stop | `cooldown.after_stop_days` | 20 days |
| Block re-entry | `cooldown.block_reentry` | `true` |

**Execution order:** Update peak prices → check absolute → check trailing → activate cooldown.

If **both** triggers fire, absolute takes priority.

---

### 3.10 `walk_forward.py` — Backtesting Framework

**Class `WalkForwardAnalyzer`**

```python
analyzer = WalkForwardAnalyzer(config, preprocessor)

# Generate periods
result = analyzer.generate_periods(
    start_date="2020-01-01",
    end_date="2023-12-31",
    min_train_periods=26,       # defaults to config.history.minimum_history_weeks
    window_type="expanding",    # or "rolling"
    rolling_window_size=52,     # required if window_type="rolling"
    rebalance_frequency="weekly" # or "monthly"
)

# Full backtest with strategy callback
wf_result, strategy_results = analyzer.run_backtest(
    start_date, end_date,
    strategy_func=my_strategy_fn,  # (period, data) → result
    verbose=True
)
```

**Anti-lookahead validation:** `validate_no_lookahead(decision_date, data)` raises `ValueError` on violation.

---

### 3.11 `utils/robust_stats.py` — Robust Statistics

| Function | Description |
|---|---|
| `compute_mad(series, window)` | Median Absolute Deviation; rolling or static |
| `robust_zscore(series, window, center_metric)` | MAD-based Z-score; caps at ±10 when MAD < 1e-6 |
| `compute_information_ratio(returns, benchmark, lookback, robust)` | Mean excess / MAD; falls back to std if MAD=0 |
| `scale_mad_to_std(mad)` | Multiply by 1.4826 for normal-equivalent |
| `detect_outliers_mad(series, window, threshold)` | Boolean mask for \|Z\| > threshold |
| `winsorize_by_mad(series, window, n_mad)` | Cap extremes at ±n_mad from median |

---

### 3.12 `utils/calendar_utils.py` — Trading Calendar

Uses `pandas_market_calendars` (default exchange: **NYSE**).

| Function | Description |
|---|---|
| `get_trading_calendar(start, end, exchange)` | Valid trading days (excludes holidays/weekends) |
| `get_week_end_dates(start, end, exchange)` | Last trading day of each ISO week |
| `is_trading_day(date, exchange)` | Boolean check |
| `trading_days_between(start, end, inclusive)` | Count with boundary control |
| `get_next_trading_day(date, n_days)` | Skip N trading days forward |
| `get_previous_trading_day(date, n_days)` | Skip N trading days backward |
| `align_to_trading_day(date, method)` | Snap to nearest valid day (`forward`/`backward`/`nearest`) |

---

## 4. YAML Configuration Reference

```yaml
# ── Paths ──
paths:
  data_root: ./data/fmp_daily          # {SYMBOL}_daily.csv location
  output_root: ./src/strategies/output
  state_dir:   .../state/adaptive_rotation
  audit_dir:   .../audit/adaptive_rotation
  weights_dir: .../weights/adaptive_rotation

# ── Dates ──
dates:
  start_date: 2017-01-01
  end_date: null                       # null = latest

history:
  minimum_history_weeks: 26

# ── Benchmark ──
benchmark:
  excess_return_benchmark: QQQ

# ── Asset Groups (3 groups × ~20-27 symbols each) ──
asset_groups:
  group_a_growth_tech:   { max_assets: 2, symbols: [AAPL, MSFT, NVDA, ...] }  # 20 symbols
  group_b_real_assets:   { max_assets: 2, symbols: [XOM, CVX, GLD, ...] }     # 25 symbols
  group_c_defensive:     { max_assets: 2, symbols: [TLT, IEF, XLU, ...] }     # 27 symbols

# ── Strategy Metadata ──
strategy:
  name: adaptive_multi_asset_rotation
  version: v1.2.1
  base_frequency: daily
  rebalance_frequency: weekly
```

---

## 5. How to Run

### 5.1 Single Decision Point

```python
from src.strategies.adaptive_rotation import AdaptiveRotationEngine

engine = AdaptiveRotationEngine(
    config_path="src/strategies/AdaptiveRotationConf_v1.2.1.yaml"
)

weights, audit = engine.run(
    price_data=weekly_prices_dict,   # Dict[str, pd.Series]
    as_of_date="2024-06-30"
)

print(f"Invested: {weights.get_invested_weight():.1%}")
print(f"Cash:     {weights.cash_weight:.1%}")
print(f"Regime:   {weights.regime_state}")
print(f"Weights:  {weights.weights}")

# Save audit trail
audit.to_json("output/audit/2024-06-30.json")
```

### 5.2 Walk-Forward Backtest

```python
from src.strategies.adaptive_rotation.config_loader import load_config
from src.strategies.adaptive_rotation.data_preprocessor import DataPreprocessor
from src.strategies.adaptive_rotation.walk_forward import WalkForwardAnalyzer
from src.strategies.adaptive_rotation import AdaptiveRotationEngine

config = load_config("src/strategies/AdaptiveRotationConf_v1.2.1.yaml")
preprocessor = DataPreprocessor(config)
preprocessor.load_and_prepare()

engine = AdaptiveRotationEngine(config=config, data_preprocessor=preprocessor)
analyzer = WalkForwardAnalyzer(config, preprocessor)

def strategy_step(period, data):
    weights, audit = engine.run(data, period.decision_date)
    return {"date": period.decision_date, "weights": weights, "audit": audit}

wf_result, results = analyzer.run_backtest(
    start_date="2020-01-01",
    end_date="2024-12-31",
    strategy_func=strategy_step,
    window_type="expanding",
    rebalance_frequency="weekly"
)

# Export to CSV
valid = [r for r in results if r is not None]
df = AdaptiveRotationEngine.export_weights_to_dataframe(valid)
df.to_csv("output/weights/backtest_weights.csv", index=False)
```

### 5.3 Running Individual Module Tests

Each module has a `if __name__ == "__main__"` block:

```bash
# From project root
python -m src.strategies.adaptive_rotation.config_loader
python -m src.strategies.adaptive_rotation.data_preprocessor
python -m src.strategies.adaptive_rotation.market_regime
python -m src.strategies.adaptive_rotation.group_strength
python -m src.strategies.adaptive_rotation.intra_group_ranking
python -m src.strategies.adaptive_rotation.exception_framework
python -m src.strategies.adaptive_rotation.risk_manager
python -m src.strategies.adaptive_rotation.walk_forward
python -m src.strategies.adaptive_rotation.adaptive_rotation_engine
```

---

## 6. Dependencies

```
pandas
numpy
pydantic
pyyaml
pandas_market_calendars
```

---

## 7. Key Design Principles

| Principle | Implementation |
|---|---|
| **No Lookahead Bias** | `get_data_as_of_date()` + `validate_no_lookahead()` enforce point-in-time |
| **Robust Statistics** | MAD replaces std in Z-scores and IR; guards against outlier distortion |
| **Regime-First** | Risk budget is set by regime *before* any asset selection occurs |
| **Explainability** | `AuditLog` serializes every signal, threshold, and decision to JSON |
| **Fail-Safe** | Fallback portfolio (SPY/QQQ/IAU/XLU/XLV) when no groups qualify |
| **Modular** | Each module is independently testable with `__main__` blocks |

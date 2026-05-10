# Weight Allocation Guide

## Overview

The ML strategy module now supports multiple weight allocation methods for assigning portfolio weights to selected stocks.

## Supported Weight Allocation Methods

### 1. Equal Weight - Default Method

Assigns equal weight to all selected stocks.

**Pros:**
- Simple and easy to understand
- No additional market data required
- Fast computation speed

**Usage:**
```python
result = strategy.generate_weights(
    data_dict,
    prediction_mode='single',
    weight_method='equal'
)
```

### 2. Min Variance

Constructs a minimum variance portfolio using historical return data, aiming to minimize the portfolio's volatility.

**Pros:**
- Considers correlations between stocks
- Reduces overall portfolio risk
- Better risk-adjusted returns
- **Automatically uses quarterly prices (`adj_close_q`) from fundamental data, no need to provide additional price data**

**Cons:**
- Longer computation time
- High requirements for data quality

**Usage:**
```python
# Method 1: Directly use adj_close_q from fundamental data (Recommended)
data_dict = {
    'fundamentals': fundamentals_df  # Must contain adj_close_q column
}

result = strategy.generate_weights(
    data_dict,
    prediction_mode='single',
    weight_method='min_variance',
    lookback_periods=8  # Number of lookback quarters for covariance matrix calculation (default 8, i.e., 2 years)
)

# Method 2: Use daily price data (Optional, if finer covariance estimation is needed)
data_dict = {
    'fundamentals': fundamentals_df,
    'prices': prices_df  # Contains ['date', 'tic', 'close']
}

result = strategy.generate_weights(
    data_dict,
    prediction_mode='single',
    weight_method='min_variance',
    lookback_periods=252  # Number of lookback days for covariance matrix calculation
)
```

## Price Data Format Requirements

When using the `min_variance` method, two data formats are supported:

### Format 1: Fundamental Data (Recommended, used automatically)
If the fundamental data contains the following columns, the system will use them automatically:
- `datadate`: Quarter date
- `gvkey` or `tic`: Stock identifier
- `adj_close_q`: Quarterly adjusted close price

Example:
```python
fundamentals_df = pd.DataFrame({
    'datadate': ['2024-01-31', '2024-04-30', ...],
    'gvkey': ['001055', '001055', ...],
    'adj_close_q': [72.56, 75.06, ...],
    # ... other fundamental indicators
})
```

### Format 2: Daily Price Data (Optional)
If daily data is needed for a more precise covariance estimation:
- `date`: Date
- `tic` or `gvkey`: Stock identifier
- `close` or `adj_close`: Close price

Example:
```python
prices_df = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-02', ...],
    'tic': ['AAPL', 'AAPL', ...],
    'close': [150.5, 152.3, ...]
})
```

## Complete Examples

### Example 1: Single Prediction + Equal Weight
```python
from src.strategies.ml_strategy import MLStockSelectionStrategy
from src.strategies.base_strategy import StrategyConfig

config = StrategyConfig(
    name="ML Stock Selection",
    description="Machine learning based stock selection"
)

strategy = MLStockSelectionStrategy(config)

data_dict = {
    'fundamentals': fundamentals_df  # Contains y_return column
}

result = strategy.generate_weights(
    data_dict,
    test_quarters=4,
    top_quantile=0.75,
    prediction_mode='single',
    weight_method='equal'
)

print(result.weights)
```

### Example 2: Rolling Prediction + Min Variance (Using Fundamental Data)
```python
# Only fundamental data is needed, adj_close_q column will be used automatically
data_dict = {
    'fundamentals': fundamentals_df  # Contains adj_close_q column
}

result = strategy.generate_weights(
    data_dict,
    test_quarters=4,
    top_quantile=0.75,
    prediction_mode='rolling',
    weight_method='min_variance',
    lookback_periods=8  # Look back 8 quarters
)

print(result.weights)
```

### Example 3: Sector Neutral Strategy + Min Variance (Using Fundamental Data)
```python
from src.strategies.ml_strategy import SectorNeutralMLStrategy

sector_config = StrategyConfig(
    name="Sector Neutral ML",
    description="Sector-neutral ML strategy"
)

sector_strategy = SectorNeutralMLStrategy(sector_config)

# Only fundamental data is needed, adj_close_q column will be used automatically
data_dict = {
    'fundamentals': fundamentals_df  # Contains sector/gsector and adj_close_q columns
}

result = sector_strategy.generate_weights(
    data_dict,
    test_quarters=4,
    top_quantile=0.75,
    prediction_mode='rolling',
    weight_method='min_variance',
    lookback_periods=8  # Look back 8 quarters
)

print(result.weights)
```

## Parameter Descriptions

### Common Parameters
- `prediction_mode`: Prediction mode
  - `'single'`: Single prediction (uses the last date)
  - `'rolling'`: Rolling prediction (all available dates)
  
- `weight_method`: Weight allocation method
  - `'equal'`: Equal weight (default)
  - `'min_variance'`: Minimum variance
  
- `test_quarters`: Validation window in quarters (default 4)
- `train_quarters`: Training window in quarters (default 16, used only in rolling mode)
- `top_quantile`: Stock selection quantile threshold (default 0.75, meaning selecting the top 25% stocks based on predicted returns)

### Min Variance Method Specific Parameters
- `lookback_periods`: Number of periods to look back for calculating the covariance matrix
  - When using fundamental data (`adj_close_q`): default is 8 (8 quarters, about 2 years)
  - When using daily price data: default is 252 (252 trading days, about 1 year)

## Notes

1. **Automatic Data Recognition**:
   - The system automatically detects and prioritizes the `adj_close_q` column in fundamental data.
   - If there is no price information in the fundamental data, it attempts to use additionally provided `prices` data.
   - No manual selection of the data source is necessary.

2. **Data Requirements**:
   - When using quarterly data (`adj_close_q`), at least 3 quarters are required.
   - When using daily data, at least 3 trading days are required.
   - It is recommended to use at least 8 quarters or 252 trading days to obtain a stable covariance estimate.

3. **Computational Performance**: The min variance method requires optimization solving, which takes longer than the equal weight method.

4. **Data Quality**: The min variance method is sensitive to data quality; missing values will result in some stocks being excluded.

5. **Automatic Fallback**: If the price data is insufficient or optimization fails, the system automatically falls back to the equal weight method and logs a warning.

6. **Risk Control Limits**: All weight allocation methods will apply the risk control limits set in the strategy configuration (e.g., maximum weight per stock).

## Extensions

If you need to add a new weight allocation method, you can extend the `allocate_weights` method in the `MLStockSelectionStrategy` class:

```python
def allocate_weights(self, selected_stocks, method='equal', **kwargs):
    if method == 'your_new_method':
        # Implement your weight allocation logic
        weights_df = self._compute_your_method_weights(selected_stocks, **kwargs)
    elif method == 'equal':
        weights_df = self._compute_equal_weights(selected_stocks['gvkey'].tolist())
    # ... other methods
    
    return result
```

import os
import sqlite3
import pandas as pd
import pickle
import numpy as np

def main():
    print("Generating legacy data files for fundamental_portfolio_drl.py...")
    
    os.makedirs("./data_processor", exist_ok=True)
    os.makedirs("./result", exist_ok=True)
    os.makedirs("./output", exist_ok=True)
    
    # 1. Generate sp500_tickers_daily_price_20250712.csv
    print("Exporting price data from SQLite to CSV...")
    conn = sqlite3.connect("./data/finrl_trading.db")
    
    query = """
    SELECT 
        date AS datadate,
        open AS prcod,
        close AS prccd,
        high AS prchd,
        low AS prcld,
        volume AS cshtrd,
        close / adj_close AS ajexdi,
        ticker AS gvkey
    FROM price_data
    """
    df_price = pd.read_sql_query(query, conn)
    conn.close()
    
    # Clean up ajexdi (replace inf/nan)
    df_price['ajexdi'] = df_price['ajexdi'].replace([np.inf, -np.inf], np.nan)
    df_price['ajexdi'] = df_price['ajexdi'].fillna(1.0)
    
    price_csv_path = "./data_processor/sp500_tickers_daily_price_20250712.csv"
    df_price.to_csv(price_csv_path, index=False)
    print(f"Saved {len(df_price)} price records to {price_csv_path}")
    
    # 2. Generate all_stocks_info.pickle and stock_selected.csv
    print("Processing fundamental data...")
    df_fund = pd.read_csv("./data/fundamental_data_full.csv")
    df_fund = df_fund.dropna(subset=['tradedate', 'ticker'])
    
    all_stocks_info = {}
    trade_dates = []
    
    for td, group in df_fund.groupby('tradedate'):
        df_group = pd.DataFrame({'gvkey': group['ticker'].values})
        # The DRL script converts keys to Timestamp via pd.to_datetime
        # so we will save the keys directly as strings since json/pickle often originally had strings
        # Wait, the DRL script expects to lookup by `trade_date[idx-1]` which are pandas Timestamps.
        # So the keys in the dictionary MUST be pandas Timestamps!
        ts_key = pd.to_datetime(td)
        all_stocks_info[ts_key] = df_group
        trade_dates.append(td)
        
    stocks_info_path = "./output/all_stocks_info.pickle"
    with open(stocks_info_path, 'wb') as f:
        pickle.dump(all_stocks_info, f)
    print(f"Saved all_stocks_info.pickle with {len(all_stocks_info)} trade dates.")
    
    df_selected = pd.DataFrame({'trade_date': trade_dates})
    df_selected = df_selected.sort_values('trade_date')
    selected_csv_path = "./result/stock_selected.csv"
    df_selected.to_csv(selected_csv_path, index=False)
    print(f"Saved {len(df_selected)} trade dates to {selected_csv_path}")
    
    # 3. Create dummy all_return_table.pickle
    return_table_path = "./output/all_return_table.pickle"
    with open(return_table_path, 'wb') as f:
        pickle.dump(pd.DataFrame(), f)
    print(f"Saved dummy all_return_table.pickle")
    
    print("Done! You can now run fundamental_portfolio_drl.py")

if __name__ == '__main__':
    main()

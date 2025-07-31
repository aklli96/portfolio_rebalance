import pandas as pd
from datetime import datetime
from cal_portfolio import rabalance_portfolio, read_config, fetch_ibkr_portfolio

def save_rebalance_to_excel(result_dict, config, filename="portfolio_summary.xlsx"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    row = {'Date': date_str}
    for ticker, value in result_dict.items():
        row[ticker] = value
    for i, ticker in enumerate(config['Ticker']):
        row[f"{ticker}_ratio"] = config['Ratio'].iloc[i]

    # Load all sheets
    try:
        all_sheets = pd.read_excel(filename, sheet_name=None)
    except FileNotFoundError:
        all_sheets = {}

    # Work with the rebalancing_overview sheet
    df = all_sheets.get("rebalancing_overview", pd.DataFrame())
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    # Expand columns for any new tickers or ratios
    all_tickers = set()
    for col in df.columns:
        if col not in ['Date']:
            all_tickers.add(col)
    for ticker in result_dict.keys():
        all_tickers.add(ticker)
        all_tickers.add(f"{ticker}_ratio")
    for ticker in all_tickers:
        if ticker not in df.columns:
            df[ticker] = 0
    ticker_cols = sorted([t for t in all_tickers if not t.endswith('_ratio')])
    ratio_cols = sorted([t for t in all_tickers if t.endswith('_ratio')])
    df = df[['Date'] + ticker_cols + ratio_cols]
    df = df.fillna(0)

    # Update the sheet in the dict
    all_sheets["rebalancing_overview"] = df

    # Write all sheets back
    with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
        for sheet, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Rebalance summary saved to {filename} (sheet: rebalancing_overview)")

import pandas as pd
from datetime import datetime
from cal_portfolio import rabalance_portfolio, read_config, fetch_ibkr_portfolio

def save_rebalance_to_excel(config, filename="portfolio_summary.xlsx"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    row = {'Rebalance_Date': date_str}

    # Load all sheets
    try:
        all_sheets = pd.read_excel(filename, sheet_name=None)
    except FileNotFoundError:
        all_sheets = {}

    # Work with the rebalancing_overview sheet
    df = all_sheets.get("rebalancing_overview", pd.DataFrame())

    # Get all historical tickers
    historical_tickers = set(df.columns) - {'Rebalance_Date'} if not df.empty else set()
    current_tickers = set(config['Ticker'])
    all_tickers = sorted(historical_tickers | current_tickers)

    # Prepare current ratios for all tickers
    for ticker in all_tickers:
        if ticker in current_tickers:
            idx = list(config['Ticker']).index(ticker)
            row[ticker] = config['Ratio'].iloc[idx]
        else:
            row[ticker] = 0.0

    # If the sheet is empty, just add the first row with (0%) change
    if df.empty:
        for ticker in all_tickers:
            ratio = row[ticker]
            row[ticker] = f"{ratio:.2%} (+0.00%)"
        df = pd.DataFrame([row])
    else:
        # Calculate ratio change for each ticker
        last_row = df.iloc[-1]
        for ticker in all_tickers:
            current_ratio = row[ticker]
            prev_ratio_str = last_row.get(ticker, "0.00% (+0.00%)").split()[0].replace('%','')
            prev_ratio = float(prev_ratio_str) / 100 if prev_ratio_str else 0
            change = current_ratio - prev_ratio
            row[ticker] = f"{current_ratio:.2%} ({change:+.2%})"
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    # Keep only Rebalance_Date and all tickers columns
    columns = ['Rebalance_Date'] + list(all_tickers)
    df = df[columns]

    # Highlight cells with 0% ratio for 3 consecutive rebalance dates
    def highlight_consecutive_zero(s):
        # Only apply to ticker columns, skip Rebalance_Date
        if s.name == 'Rebalance_Date':
            return [''] * len(s)
        zero_mask = []
        # Extract ratio float from string like "0.00% (+0.00%)"
        for val in s:
            ratio_str = str(val).split()[0].replace('%', '')
            try:
                ratio = float(ratio_str) / 100
            except Exception:
                ratio = None
            zero_mask.append(ratio == 0)
        # Find 3 consecutive zeros
        highlight = [''] * len(s)
        for i in range(2, len(s)):
            if zero_mask[i] and zero_mask[i-1] and zero_mask[i-2]:
                highlight[i] = 'background-color: yellow'
        return highlight

    styled_df = df.style.apply(highlight_consecutive_zero, subset=all_tickers)

    # Update the sheet in the dict
    all_sheets["rebalancing_overview"] = df

    # Write all sheets back, using Styler for the overview sheet
    with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
        for sheet, sheet_df in all_sheets.items():
            if sheet == "rebalancing_overview":
                styled_df.to_excel(writer, sheet_name=sheet, index=False)
            else:
                sheet_df.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Rebalance summary saved to {filename} (sheet: rebalancing_overview)")

def save_performance_to_excel(result_dict, filename="portfolio_summary.xlsx"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    columns = ['report_gen_date', 'ticker', 'avg_price', 'market_price', 'performance']

    # Load all sheets
    try:
        all_sheets = pd.read_excel(filename, sheet_name=None)
    except FileNotFoundError:
        all_sheets = {}

    # Work with the performance sheet
    df = all_sheets.get("Performance", pd.DataFrame(columns=columns))

    for ticker, data in result_dict.items():
        avg_price = float(f"{data['avg_price']:.2f}")
        market_price = float(f"{data['market_price']:.2f}")
        if avg_price and avg_price != 0:
            perf = market_price - avg_price
            perf_pct = (market_price - avg_price) / avg_price
        else:
            perf = 0.0
            perf_pct = 0.0
        new_row = {
            'report_gen_date': date_str,
            'ticker': ticker,
            'avg_price': avg_price,
            'market_price': market_price,
            'performance': f"{perf:.2f} ({perf_pct:+.2%})"
        }

        # Check if a row for this date and ticker exists
        mask = (df['report_gen_date'] == date_str) & (df['ticker'] == ticker)
        if mask.any():
            # Update the existing row, cast all to str
            df.loc[mask, columns[2:]] = [
                avg_price,
                market_price,
                str(new_row['performance'])
            ]
        else:
            # Append new row, cast all to str
            df = pd.concat([df, pd.DataFrame([new_row], columns=columns)], ignore_index=True)
    
    # Ensure avg_price and market_price columns are float with 2 decimals
    df['avg_price'] = df['avg_price'].astype(float).round(2)
    df['market_price'] = df['market_price'].astype(float).round(2)
    # Update the sheet in the dict
    all_sheets["Performance"] = df[columns]

    # Write all sheets back
    with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
        for sheet, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet, index=False)
    print(f"Performance report saved to {filename} (sheet: Performance)")
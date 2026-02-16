import pandas as pd
from datetime import datetime


def _load_all_sheets(filename):
    """Load all sheets from an Excel file, returning {} if the file doesn't exist."""
    try:
        return pd.read_excel(filename, sheet_name=None)
    except FileNotFoundError:
        return {}


def _write_all_sheets(all_sheets, filename, styled_sheet=None, styled_df=None):
    """Write all sheets back to an Excel file, optionally using a Styler for one sheet."""
    with pd.ExcelWriter(filename, mode="w", engine="openpyxl") as writer:
        for sheet, sheet_df in all_sheets.items():
            if styled_sheet and sheet == styled_sheet and styled_df is not None:
                styled_df.to_excel(writer, sheet_name=sheet, index=False)
            else:
                sheet_df.to_excel(writer, sheet_name=sheet, index=False)


def _parse_ratio_from_str(val):
    """Extract the float ratio from a string like '12.50% (+0.50%)'."""
    ratio_str = str(val).split()[0].replace('%', '')
    try:
        return float(ratio_str) / 100
    except (ValueError, IndexError):
        return 0.0


def save_rebalance_to_excel(config, filename="portfolio_summary.xlsx"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    all_sheets = _load_all_sheets(filename)
    df = all_sheets.get("rebalancing_overview", pd.DataFrame())

    historical_tickers = set(df.columns) - {'Rebalance_Date'} if not df.empty else set()
    current_tickers = set(config['Ticker'])
    all_tickers = sorted(historical_tickers | current_tickers)

    # Build a ticker→ratio lookup from config
    config_ratios = dict(zip(config['Ticker'], config['Ratio']))
    row = {'Rebalance_Date': date_str}
    for ticker in all_tickers:
        row[ticker] = config_ratios.get(ticker, 0.0)

    if df.empty:
        for ticker in all_tickers:
            row[ticker] = f"{row[ticker]:.2%} (+0.00%)"
        df = pd.DataFrame([row])
    else:
        last_row = df.iloc[-1]
        for ticker in all_tickers:
            current_ratio = row[ticker]
            prev_ratio = _parse_ratio_from_str(last_row.get(ticker, "0.00% (+0.00%)"))
            change = current_ratio - prev_ratio
            row[ticker] = f"{current_ratio:.2%} ({change:+.2%})"
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    columns = ['Rebalance_Date'] + list(all_tickers)
    df = df[columns]

    def highlight_consecutive_zero(s):
        if s.name == 'Rebalance_Date':
            return [''] * len(s)
        zero_mask = [_parse_ratio_from_str(val) == 0 for val in s]
        highlight = [''] * len(s)
        for i in range(2, len(s)):
            if zero_mask[i] and zero_mask[i-1] and zero_mask[i-2]:
                highlight[i] = 'background-color: yellow'
        return highlight

    styled_df = df.style.apply(highlight_consecutive_zero, subset=all_tickers)
    all_sheets["rebalancing_overview"] = df
    _write_all_sheets(all_sheets, filename, styled_sheet="rebalancing_overview", styled_df=styled_df)
    print(f"Rebalance summary saved to {filename} (sheet: rebalancing_overview)")


def save_performance_to_excel(result_dict, filename="portfolio_summary.xlsx"):
    date_str = datetime.now().strftime("%Y-%m-%d")
    columns = ['report_gen_date', 'ticker', 'avg_price', 'market_price', 'performance']

    all_sheets = _load_all_sheets(filename)
    df = all_sheets.get("Performance", pd.DataFrame(columns=columns))

    for ticker, data in result_dict.items():
        avg_price = round(data['avg_price'], 2)
        market_price = round(data['market_price'], 2)

        if avg_price != 0:
            perf = market_price - avg_price
            perf_pct = perf / avg_price
        else:
            perf = 0.0
            perf_pct = 0.0

        perf_str = f"{perf:.2f} ({perf_pct:+.2%})"
        mask = (df['report_gen_date'] == date_str) & (df['ticker'] == ticker)
        if mask.any():
            df.loc[mask, ['avg_price', 'market_price', 'performance']] = [avg_price, market_price, perf_str]
        else:
            new_row = {
                'report_gen_date': date_str, 'ticker': ticker,
                'avg_price': avg_price, 'market_price': market_price,
                'performance': perf_str
            }
            df = pd.concat([df, pd.DataFrame([new_row], columns=columns)], ignore_index=True)

    df['avg_price'] = df['avg_price'].astype(float).round(2)
    df['market_price'] = df['market_price'].astype(float).round(2)
    all_sheets["Performance"] = df[columns]
    _write_all_sheets(all_sheets, filename)
    print(f"Performance report saved to {filename} (sheet: Performance)")
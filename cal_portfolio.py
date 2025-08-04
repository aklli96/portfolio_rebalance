import pandas as pd
import sys
from ib_insync import IB

def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float)/100
    return config

def validation(config):
    if round(config['Ratio'].sum(),3) != 1:
        print(f"your portfolio ratio is not equal to 1, current ratio is {config['Ratio'].sum()}, please adjust the ratio until sum of the portfolio = 1")
        sys.exit()
    else:
        print("Validation passed")
        print("Calculating the gap between the existing amount and adjusted amount")

def fetch_ibkr_portfolio():
    ib = IB()
    # Connect to IB Gateway (default port is 4002, TWS is 7497)
    ib.connect('127.0.0.1', 4002, clientId=1)
    positions = ib.positions()
    # Get account summary for cash
    account_summary = ib.accountSummary()
    # Extract cash balance (Base Currency)
    cash = None
    for item in account_summary:
        if item.tag == 'TotalCashValue':
            cash = float(item.value)
            break
    # Convert positions to a DataFrame
    data = []
    for pos in positions:
        ticker_data = ib.reqMktData(pos.contract, '', False, False)
        ib.sleep(1)  # Give time for price to update
        market_price = ticker_data.marketPrice() if ticker_data.marketPrice() is not None else 0
        data.append({
            'Ticker': pos.contract.symbol,
            'Quantity': pos.position,
            'AvgCost': pos.avgCost,
            'MarketPrice': market_price,
            'CurrentValue': pos.position * market_price
        })
    # Add cash as a row in the DataFrame
    data.append({
        'Ticker': 'CASH',
        'Quantity': None,
        'AvgCost': None,
        'MarketPrice': None,
        'CurrentValue': cash
    })
    df = pd.DataFrame(data)
    return df

def rabalance_portfolio(config, current_position, output_callback=None):
    def default_output(msg):
        print(msg)

    output = output_callback if output_callback is not None else default_output

    validation(config)
    dict = {}
    # Merge MarketPrice into config for calculation
    market_info = current_position[['Ticker', 'CurrentValue', 'MarketPrice']]
    fetched_portfolio = config.merge(market_info, on='Ticker', how='left')
    fetched_portfolio.fillna(0, inplace=True)
    amount_in_pool = fetched_portfolio['CurrentValue'].sum()
    output("Depending on your ratio setting, please make the following adjustment in order to rebalance your portfolio:")
    for i in range(len(fetched_portfolio['Ratio'])):
        tb_changed_amt = (amount_in_pool * fetched_portfolio['Ratio'][i]) - fetched_portfolio['CurrentValue'][i]
        market_price = fetched_portfolio['MarketPrice'][i]
        ticker = fetched_portfolio['Ticker'][i]
        if market_price and market_price > 0:
            shares_to_trade = tb_changed_amt / market_price
        else:
            shares_to_trade = 0
        action = "Buy" if tb_changed_amt > 0 else "Sell"
        output(f"{action} {abs(shares_to_trade):.2f} shares of {ticker} (amount: {abs(tb_changed_amt):.2f})")
        output(f"  - Amount: {tb_changed_amt:.2f}, Shares: {shares_to_trade:.2f}")
        dict[ticker] = {'amount': tb_changed_amt, 'shares': shares_to_trade}
    return dict
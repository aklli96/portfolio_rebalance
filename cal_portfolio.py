import pandas as pd
from ib_insync import IB
import math

def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float)/100
    return config

def validation(config, output_callback=None):
    def default_output(msg):
        print(msg)
    
    output = output_callback if output_callback is not None else default_output
    
    if round(config['Ratio'].sum(),3) != 1:
        msg = f"Your portfolio ratio is not equal to 1, current ratio is {config['Ratio'].sum():.3%}, please adjust the ratio until sum of the portfolio = 1"
        output(msg)
        return False
    else:
        output("Validation passed")
        output("Calculating the gap between the existing amount and adjusted amount")
        return True

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
        ib.reqMarketDataType(3)
        ticker_data = ib.reqMktData(pos.contract, snapshot=True)
        ib.sleep(10)  # Give time for price to update
        market_price = ticker_data.marketPrice() if ticker_data.marketPrice() != -1 else ticker_data.close
        data.append({
            'Ticker': pos.contract.symbol,
            'Quantity': pos.position,
            'AvgCost': pos.avgCost,
            'MarketPrice': market_price,
            'CurrentValue': round(pos.position * market_price,2)
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
    return df, ib

def rabalance_portfolio(config, current_position, output_callback=None):
    def default_output(msg):
        print(msg)

    output = output_callback if output_callback is not None else default_output

    if not validation(config, output):
        return None
    dict = {}
    # Merge MarketPrice into config for calculation
    market_info = current_position[['Ticker', 'Quantity', 'AvgCost', 'CurrentValue', 'MarketPrice']]
    fetched_portfolio = config.merge(market_info, on='Ticker', how='left')
    fetched_portfolio.fillna(0, inplace=True)
    tradable_funds = fetched_portfolio[fetched_portfolio['Ticker'] == 'CASH']['CurrentValue'].values[0]
    amount_in_pool = fetched_portfolio['CurrentValue'].sum()
    output("Depending on your ratio setting, please make the following adjustment in order to rebalance your portfolio:")
    for i in range(len(fetched_portfolio['Ratio'])):
        if fetched_portfolio['Ticker'][i] == 'CASH' or fetched_portfolio['Ratio'][i] <= 0:
            continue
        else:
            tb_changed_amt = (amount_in_pool * fetched_portfolio['Ratio'][i]) - (fetched_portfolio['AvgCost'][i] * fetched_portfolio['Quantity'][i])
            market_price = fetched_portfolio['MarketPrice'][i]
            avg_price = fetched_portfolio['AvgCost'][i]
            ticker = fetched_portfolio['Ticker'][i]
            shares_to_trade = tb_changed_amt / market_price if tb_changed_amt > 0 else abs(tb_changed_amt) / market_price
            if shares_to_trade < 1:
                shares_to_trade = 0
                tradable_funds = tradable_funds
                action = "to be changed amount is less than the market price, no action required"
                
            else:
                shares_to_trade = math.floor(shares_to_trade)
                action = "Buy" if tb_changed_amt > 0 else "Sell"
                tradable_funds = tradable_funds + (shares_to_trade * market_price) if action == 'Sell' else tradable_funds
        dict[ticker] = {'tb_changed': abs(tb_changed_amt), 'avg_price':avg_price, 'market_price': market_price, 'shares': shares_to_trade, 'action': action}
    
    for ticker in dict:
        if dict[ticker]['shares'] > 0 and dict[ticker]['action'] == "Buy":
            output(f"{dict[ticker]['action']} {dict[ticker]['shares']} shares of {ticker}")
            tradable_funds = tradable_funds - (dict[ticker]['shares'] * dict[ticker]['market_price'])
        elif dict[ticker]['shares'] > 0 and dict[ticker]['action'] == "Sell":
            output(f"{dict[ticker]['action']} {dict[ticker]['shares']} shares of {ticker}")
        else:
            output(f"ticker: {ticker} {dict[ticker]['action']}")
    return dict
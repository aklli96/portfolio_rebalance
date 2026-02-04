import pandas as pd
from ib_insync import IB
import math
from datetime import timedelta

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

def ibkr_conn():
    ib = IB()
    # Connect to IB Gateway (default port is 4002, TWS is 7497)
    ib_conn = ib.connect('127.0.0.1', 4002, clientId=1)
    return ib_conn

def fetch_ibkr_portfolio(ib):
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
    last_timestamp = None

    for pos in positions:
        if hasattr(pos.contract, 'right') and pos.contract.right in ('P', 'C'):
            pos.contract.exchange = 'SMART'
            bars = ib.reqHistoricalData(
                pos.contract,
                endDateTime="", # Empty string for current time
                durationStr='30 D', # Request 1 day of data
                barSizeSetting='1 hour', # Bar size (e.g., '1 day', '1 hour', '1 min')
                whatToShow='TRADES', # Data type: 'TRADES', 'MIDPOINT', 'BID', 'ASK', etc.
                useRTH=True, # Use regular trading hours only
                formatDate=1 # 1 for yyyyMMdd HH:mm:ss, 2 for epoch time
            )
            df = pd.DataFrame(bars)
            latest_close_price = df['close'].iloc[-1]
            market_price = latest_close_price * 100
            data.append({
                'Ticker': f"{pos.contract.symbol} {pos.contract.right if hasattr(pos.contract, 'right') else ''}",
                'Quantity': pos.position,
                'AvgCost': pos.avgCost,
                'MarketPrice': market_price,
                'CurrentValue': round(pos.position * market_price,2),
                'LastUpdate': last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
            })
        else:
            ib.reqMarketDataType(3)
            ticker_data = ib.reqMktData(pos.contract, snapshot=True)
            ib.sleep(5)  # Give time for price to update
            market_price = ticker_data.marketPrice() if ticker_data.marketPrice() > 0 else ticker_data.close
            timestamp = None
            if hasattr(ticker_data, 'time'):
                timestamp = ticker_data.time
            elif hasattr(ticker_data, 'lastTime'):
                timestamp = ticker_data.lastTime
            if timestamp and (last_timestamp is None or timestamp > last_timestamp):
                last_timestamp = timestamp + timedelta(hours=8)                   
            data.append({
                'Ticker': pos.contract.symbol,
                'Quantity': pos.position,
                'AvgCost': pos.avgCost,
                'MarketPrice': market_price,
                'CurrentValue': round(pos.position * market_price,2),
                'LastUpdate': last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
            })
    # Add cash as a row in the DataFrame
    data.append({
        'Ticker': 'CASH',
        'Quantity': 0,
        'AvgCost': 0,
        'MarketPrice': 0,
        'CurrentValue': cash,
        'LastUpdate': last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
    })
    df = pd.DataFrame(data)
    return df

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
        ticker = fetched_portfolio['Ticker'][i]
        if ticker == 'CASH':
            target_cash = amount_in_pool * fetched_portfolio['Ratio'][i]
            current_cash = fetched_portfolio['CurrentValue'][i]
            tb_changed_amt = target_cash - current_cash
            dict[ticker] = {
                'tb_changed': abs(tb_changed_amt), 
                'avg_price': 1, 
                'market_price': 1, 
                'shares': abs(tb_changed_amt), 
                'action': 'Increase' if tb_changed_amt > 0 else 'Decrease'
            }
        else:
            target_value = amount_in_pool * fetched_portfolio['Ratio'][i]
            current_value = fetched_portfolio['CurrentValue'][i]
            tb_changed_amt = target_value - current_value
            market_price = fetched_portfolio['MarketPrice'][i]
            avg_price = fetched_portfolio['AvgCost'][i]
            current_quantity = fetched_portfolio['Quantity'][i]
            
            # Calculate shares to trade
            shares_to_trade = abs(tb_changed_amt) / market_price
            
            # For selling, can't sell more than we have
            if tb_changed_amt < 0 and shares_to_trade > current_quantity:
                shares_to_trade = current_quantity
            
            if shares_to_trade < 1:
                shares_to_trade = 0
                action = "to be changed amount is less than the market price, no action required"
            else:
                shares_to_trade = math.floor(shares_to_trade)
                action = "Buy" if tb_changed_amt > 0 else "Sell"
                if action == 'Sell':
                    tradable_funds = tradable_funds + (shares_to_trade * market_price)
                    
            dict[ticker] = {'tb_changed': abs(tb_changed_amt), 'avg_price':avg_price, 'market_price': market_price, 'shares': shares_to_trade, 'action': action}
    
    # Phase 1: Process all SELL orders first to accumulate cash
    for ticker in dict:
        if ticker != 'CASH' and dict[ticker]['shares'] > 0 and dict[ticker]['action'] == "Sell":
            tradable_funds = tradable_funds + (dict[ticker]['shares'] * dict[ticker]['market_price'])
            output(f"Sell {dict[ticker]['shares']} shares of {ticker} to free up ${dict[ticker]['shares'] * dict[ticker]['market_price']:.2f}")
    
    # Phase 2: Check CASH target and reserve needed cash
    target_cash = amount_in_pool * fetched_portfolio[fetched_portfolio['Ticker'] == 'CASH']['Ratio'].values[0]
    current_cash = fetched_portfolio[fetched_portfolio['Ticker'] == 'CASH']['CurrentValue'].values[0]
    
    if 'CASH' in dict:
        cash_needed = target_cash - current_cash
        if cash_needed > 0:
            output(f"Reserve ${cash_needed:.2f} in CASH to meet {fetched_portfolio[fetched_portfolio['Ticker'] == 'CASH']['Ratio'].values[0]:.2%} target")
            tradable_funds = tradable_funds - cash_needed
        elif cash_needed < 0:
            output(f"Release ${abs(cash_needed):.2f} from CASH (exceeds {fetched_portfolio[fetched_portfolio['Ticker'] == 'CASH']['Ratio'].values[0]:.2%} target)")
            tradable_funds = tradable_funds - cash_needed  # cash_needed is negative, so this adds to tradable_funds
    
    # Phase 3: Process BUY orders with remaining funds
    for ticker in dict:
        if ticker != 'CASH' and dict[ticker]['shares'] > 0 and dict[ticker]['action'] == "Buy":
            if tradable_funds >= dict[ticker]['market_price']:
                n = 0
                while n < dict[ticker]['shares'] and tradable_funds >= dict[ticker]['market_price']:
                    tradable_funds = tradable_funds - dict[ticker]['market_price']
                    n = n + 1
                if n > 0:
                    output(f"Buy {n} shares of {ticker} for ${n * dict[ticker]['market_price']:.2f}")
                if n < dict[ticker]['shares']:
                    output(f"Warning: Insufficient funds to buy all {dict[ticker]['shares']} shares of {ticker}, only bought {n} shares")
            else:
                output(f"Warning: Insufficient funds to buy {ticker}, ${tradable_funds:.2f} available but ${dict[ticker]['market_price']:.2f} needed per share")
        elif ticker != 'CASH' and dict[ticker]['shares'] == 0:
            output(f"{ticker} - no action required (change amount less than market price)")
    
    if tradable_funds > 0:
        output(f"Remaining available funds: ${tradable_funds:.2f}")
    
    return dict
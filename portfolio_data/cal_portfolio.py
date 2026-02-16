import pandas as pd
from ib_insync import IB
import math
from datetime import timedelta


def _resolve_output(output_callback):
    """Return the output callback or a default print fallback."""
    return output_callback if output_callback is not None else print


def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float) / 100
    return config


def validation(config, output_callback=None):
    output = _resolve_output(output_callback)
    ratio_sum = round(config['Ratio'].sum(), 3)
    if ratio_sum != 1:
        output(f"Your portfolio ratio is not equal to 1, current ratio is {ratio_sum:.3%}, "
               f"please adjust the ratio until sum of the portfolio = 1")
        return False
    output("Validation passed")
    output("Calculating the gap between the existing amount and adjusted amount")
    return True


def ibkr_conn():
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    return ib


def _fetch_option_price(ib, contract):
    """Fetch latest price for an option contract via historical data."""
    contract.exchange = 'SMART'
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr='30 D',
        barSizeSetting='1 hour',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )
    df = pd.DataFrame(bars)
    return df['close'].iloc[-1] * 100


def _fetch_stock_price(ib, contract):
    """Fetch latest price for a stock/ETF contract via snapshot market data."""
    ib.reqMarketDataType(3)
    ticker_data = ib.reqMktData(contract, snapshot=True)
    ib.sleep(5)
    price = ticker_data.marketPrice()
    market_price = price if price > 0 else ticker_data.close
    timestamp = getattr(ticker_data, 'time', None) or getattr(ticker_data, 'lastTime', None)
    return market_price, timestamp


def fetch_ibkr_portfolio(ib):
    positions = ib.positions()
    account_summary = ib.accountSummary()

    cash = next(
        (float(item.value) for item in account_summary if item.tag == 'TotalCashValue'),
        0.0
    )

    data = []
    last_timestamp = None

    for pos in positions:
        contract = pos.contract
        is_option = getattr(contract, 'right', '') in ('P', 'C')

        if is_option:
            market_price = _fetch_option_price(ib, contract)
            ticker = f"{contract.symbol} {contract.right}"
        else:
            market_price, timestamp = _fetch_stock_price(ib, contract)
            ticker = contract.symbol
            if timestamp and (last_timestamp is None or timestamp > last_timestamp):
                last_timestamp = timestamp + timedelta(hours=8)

        last_update = last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
        data.append({
            'Ticker': ticker,
            'Quantity': pos.position,
            'AvgCost': pos.avgCost,
            'MarketPrice': market_price,
            'CurrentValue': round(pos.position * market_price, 2),
            'LastUpdate': last_update
        })

    # Add cash row
    last_update = last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
    data.append({
        'Ticker': 'CASH', 'Quantity': 0, 'AvgCost': 0,
        'MarketPrice': 0, 'CurrentValue': cash, 'LastUpdate': last_update
    })

    return pd.DataFrame(data)


def rabalance_portfolio(config, current_position, output_callback=None):
    output = _resolve_output(output_callback)

    if not validation(config, output):
        return None

    # Merge market data into config
    market_info = current_position[['Ticker', 'Quantity', 'AvgCost', 'CurrentValue', 'MarketPrice']]
    portfolio = config.merge(market_info, on='Ticker', how='left').fillna(0)

    amount_in_pool = portfolio['CurrentValue'].sum()
    cash_mask = portfolio['Ticker'] == 'CASH'
    tradable_funds = portfolio.loc[cash_mask, 'CurrentValue'].values[0]
    cash_ratio = portfolio.loc[cash_mask, 'Ratio'].values[0]

    output("Depending on your ratio setting, please make the following adjustment in order to rebalance your portfolio:")

    # Build trade plan for all tickers
    trade_plan = {}
    for _, row in portfolio.iterrows():
        ticker = row['Ticker']
        target_value = amount_in_pool * row['Ratio']
        current_value = row['CurrentValue']
        tb_changed_amt = target_value - current_value

        if ticker == 'CASH':
            trade_plan[ticker] = {
                'tb_changed': abs(tb_changed_amt),
                'avg_price': 1,
                'market_price': 1,
                'shares': abs(tb_changed_amt),
                'action': 'Increase' if tb_changed_amt > 0 else 'Decrease'
            }
            continue

        market_price = row['MarketPrice']
        shares_to_trade = abs(tb_changed_amt) / market_price if market_price > 0 else 0

        # Can't sell more than we hold
        if tb_changed_amt < 0:
            shares_to_trade = min(shares_to_trade, row['Quantity'])

        if shares_to_trade < 1:
            shares_to_trade = 0
            action = "to be changed amount is less than the market price, no action required"
        else:
            shares_to_trade = math.floor(shares_to_trade)
            action = "Buy" if tb_changed_amt > 0 else "Sell"

        trade_plan[ticker] = {
            'tb_changed': abs(tb_changed_amt),
            'avg_price': row['AvgCost'],
            'market_price': market_price,
            'shares': shares_to_trade,
            'action': action
        }

    # Phase 1: Process SELL orders — accumulate cash
    for ticker, info in trade_plan.items():
        if ticker != 'CASH' and info['shares'] > 0 and info['action'] == 'Sell':
            proceeds = info['shares'] * info['market_price']
            tradable_funds += proceeds
            output(f"Sell {info['shares']} shares of {ticker} to free up ${proceeds:.2f}")

    # Phase 2: Reserve / release CASH to meet target
    if 'CASH' in trade_plan:
        current_cash = portfolio.loc[cash_mask, 'CurrentValue'].values[0]
        cash_needed = (amount_in_pool * cash_ratio) - current_cash
        if cash_needed > 0:
            output(f"Reserve ${cash_needed:.2f} in CASH to meet {cash_ratio:.2%} target")
        elif cash_needed < 0:
            output(f"Release ${abs(cash_needed):.2f} from CASH (exceeds {cash_ratio:.2%} target)")
        tradable_funds -= cash_needed

    # Phase 3: Process BUY orders with remaining funds
    for ticker, info in trade_plan.items():
        if ticker == 'CASH':
            continue
        if info['shares'] > 0 and info['action'] == 'Buy':
            price = info['market_price']
            if tradable_funds >= price:
                affordable = min(info['shares'], int(tradable_funds // price))
                tradable_funds -= affordable * price
                if affordable > 0:
                    output(f"Buy {affordable} shares of {ticker} for ${affordable * price:.2f}")
                if affordable < info['shares']:
                    output(f"Warning: Insufficient funds to buy all {info['shares']} shares of {ticker}, only bought {affordable} shares")
            else:
                output(f"Warning: Insufficient funds to buy {ticker}, ${tradable_funds:.2f} available but ${price:.2f} needed per share")
        elif info['shares'] == 0:
            output(f"{ticker} - no action required (change amount less than market price)")

    if tradable_funds > 0:
        output(f"Remaining available funds: ${tradable_funds:.2f}")

    return trade_plan
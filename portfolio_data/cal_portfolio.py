import pandas as pd
from ib_insync import IB, Stock
import math
from datetime import datetime


def _resolve_output(output_callback):
    """Return the output callback or a default print fallback."""
    return output_callback if output_callback is not None else print


def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float) / 100
    if 'drawdown' in config.columns:
        config['drawdown'] = config['drawdown'].apply(
            lambda x: float(str(x).rstrip('%')) if str(x).strip().rstrip('%').replace('.', '', 1).isdigit() else 0
        )
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


def _get_best_price(ticker_data):
    """Extract the best available price from ticker data."""
    price = ticker_data.marketPrice()
    if price <= 0:
        price = ticker_data.last
    if price <= 0:
        price = ticker_data.close
    if price <= 0 and ticker_data.bid > 0 and ticker_data.ask > 0:
        price = (ticker_data.bid + ticker_data.ask) / 2
    return price if price > 0 else None


def _fetch_delayed_price(ib, contract):
    """Fetch delayed/last/previous close price as a fallback."""
    try:
        # Request delayed market data (type 3 = delayed-frozen, type 4 = delayed)
        ib.reqMarketDataType(4)
        ticker_data = ib.reqMktData(contract)
        ib.sleep(5)

        # Try delayed prices
        for attr in ('last', 'close', 'delayedLast', 'delayedClose'):
            price = getattr(ticker_data, attr, 0)
            if price and price > 0:
                ib.cancelMktData(contract)
                return price

        # Try bid/ask midpoint from delayed data
        bid = getattr(ticker_data, 'delayedBid', 0) or getattr(ticker_data, 'bid', 0)
        ask = getattr(ticker_data, 'delayedAsk', 0) or getattr(ticker_data, 'ask', 0)
        if bid and ask and bid > 0 and ask > 0:
            ib.cancelMktData(contract)
            return (bid + ask) / 2

        ib.cancelMktData(contract)
        return None
    except Exception as e:
        print(f"Warning: Could not fetch delayed price for {contract.symbol}: {e}")
        return None


def _fetch_option_price(ib, contract):
    """Fetch latest price for an option contract via market data."""
    try:
        contract.exchange = 'SMART'
        ib.reqMarketDataType(3)
        ticker_data = ib.reqMktData(contract, snapshot=True)
        ib.sleep(3)
        
        price = _get_best_price(ticker_data)
        timestamp = datetime.now() if price else None
        
        # Options are quoted per share but represent 100 shares
        return (price * 100, timestamp) if price else (None, None)
    except Exception as e:
        print(f"Warning: Could not fetch option price for {contract.localSymbol}: {e}")
        return None, None


def _fetch_stock_price(ib, contract):
    """Fetch latest price for a stock/ETF contract via snapshot market data."""
    try:
        ib.reqMarketDataType(3)
        ticker_data = ib.reqMktData(contract, snapshot=True)
        ib.sleep(2)
        
        price = _get_best_price(ticker_data)
        timestamp = datetime.now() if price else None
        
        return price, timestamp
    except Exception as e:
        print(f"Warning: Could not fetch stock price for {contract.symbol}: {e}")
        return None, None


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
        symbol_name = contract.localSymbol if is_option else contract.symbol
        
        print(f"Fetching price for {symbol_name}...")

        # Fetch price based on contract type
        if is_option:
            market_price, timestamp = _fetch_option_price(ib, contract)
            ticker = f"{contract.symbol} {contract.right}"
        else:
            market_price, timestamp = _fetch_stock_price(ib, contract)
            ticker = contract.symbol
        
        # Fall back to delayed/last/close price if market price unavailable
        if not market_price or market_price <= 0:
            print(f"Trying delayed/close price for {symbol_name}...")
            delayed_price = _fetch_delayed_price(ib, contract)
            if delayed_price and delayed_price > 0:
                # For options, multiply by 100 (contract multiplier)
                market_price = delayed_price * 100 if is_option else delayed_price
                timestamp = datetime.now()
                print(f"✓ Got delayed/close price for {symbol_name}: ${market_price}")
            else:
                market_price = pos.avgCost
                print(f"⚠ No delayed price available, using avgCost for {symbol_name}: ${market_price}")
        else:
            print(f"✓ Got price for {symbol_name}: ${market_price}")
        
        # Track most recent timestamp and format position timestamp
        if timestamp:
            if not last_timestamp or timestamp > last_timestamp:
                last_timestamp = timestamp
            position_update = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            position_update = 'N/A'

        data.append({
            'Ticker': ticker,
            'Quantity': pos.position,
            'AvgCost': pos.avgCost,
            'MarketPrice': market_price,
            'CurrentValue': round(pos.position * market_price, 2),
            'LastUpdate': position_update
        })

    # Add cash row
    cash_update = last_timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_timestamp else 'N/A'
    data.append({
        'Ticker': 'CASH', 'Quantity': 0, 'AvgCost': 0,
        'MarketPrice': 0, 'CurrentValue': cash, 'LastUpdate': cash_update
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
    tradable_funds = 0.0
    cash_ratio = portfolio.loc[cash_mask, 'Ratio'].values[0]
    current_cash = portfolio.loc[cash_mask, 'CurrentValue'].values[0]

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
        target_cash = amount_in_pool * cash_ratio
        cash_to_release = current_cash - target_cash
        if cash_to_release > 0:
            tradable_funds += cash_to_release
            output(f"Release ${cash_to_release:.2f} from CASH to meet {cash_ratio:.2%} target (keep ${target_cash:.2f})")
        elif cash_to_release < 0:
            tradable_funds -= abs(cash_to_release)
            output(f"Reserve ${abs(cash_to_release):.2f} into CASH to meet {cash_ratio:.2%} target")
        else:
            output(f"CASH is already at target ({cash_ratio:.2%})")

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


def calculate_withdrawal(config, current_position, withdraw_amount, output_callback=None):
    """Calculate shares to sell from each ticker to withdraw a given amount while maintaining target ratios."""
    output = _resolve_output(output_callback)

    if not validation(config, output):
        return None

    if withdraw_amount <= 0:
        output("Withdrawal amount must be greater than zero.")
        return None

    market_info = current_position[['Ticker', 'Quantity', 'AvgCost', 'CurrentValue', 'MarketPrice']]
    portfolio = config.merge(market_info, on='Ticker', how='left').fillna(0)

    total_value = portfolio['CurrentValue'].sum()
    if withdraw_amount > total_value:
        output(f"Withdrawal amount ${withdraw_amount:,.2f} exceeds total portfolio value ${total_value:,.2f}")
        return None

    remaining_value = total_value - withdraw_amount
    output(f"Current portfolio value: ${total_value:,.2f}")
    output(f"Withdrawal amount: ${withdraw_amount:,.2f}")
    output(f"Target portfolio value after withdrawal: ${remaining_value:,.2f}")
    output("")
    output("To withdraw while maintaining your target ratios, sell the following:")
    output("=" * 60)

    withdrawal_plan = {}
    total_to_sell = 0.0

    for _, row in portfolio.iterrows():
        ticker = row['Ticker']
        target_value_after = remaining_value * row['Ratio']
        current_value = row['CurrentValue']
        sell_value = current_value - target_value_after

        if ticker == 'CASH':
            cash_to_withdraw = max(sell_value, 0)
            withdrawal_plan[ticker] = {
                'current_value': current_value,
                'target_value': target_value_after,
                'sell_value': cash_to_withdraw,
                'shares': 0,
                'market_price': 1,
                'action': 'Withdraw' if cash_to_withdraw > 0 else 'No action'
            }
            if cash_to_withdraw > 0:
                output(f"CASH: Withdraw ${cash_to_withdraw:,.2f} (keep ${target_value_after:,.2f})")
                total_to_sell += cash_to_withdraw
            continue

        market_price = row['MarketPrice']
        if sell_value > 0 and market_price > 0:
            shares = math.floor(sell_value / market_price)
            shares = min(shares, int(row['Quantity']))
            actual_sell = shares * market_price
        else:
            shares = 0
            actual_sell = 0

        withdrawal_plan[ticker] = {
            'current_value': current_value,
            'target_value': target_value_after,
            'sell_value': actual_sell,
            'shares': shares,
            'market_price': market_price,
            'action': 'Sell' if shares > 0 else 'No action'
        }

        if shares > 0:
            output(f"{ticker}: Sell {shares} shares @ ${market_price:,.2f} = ${actual_sell:,.2f}")
            total_to_sell += actual_sell
        else:
            output(f"{ticker}: No action (current ${current_value:,.2f} <= target ${target_value_after:,.2f})")

    output("")
    output("=" * 60)
    output(f"Total proceeds from sales: ${total_to_sell:,.2f}")
    shortfall = withdraw_amount - total_to_sell
    if shortfall > 0.01:
        output(f"Note: ${shortfall:,.2f} shortfall due to rounding to whole shares.")
    output(f"Actual withdrawable amount: ${total_to_sell:,.2f}")

    return withdrawal_plan


def scan_drawdown(ib, config, output_callback=None):
    """Scan stocks for drawdown from their 365-day high using per-ticker thresholds from config."""
    output = _resolve_output(output_callback)

    output("Scanning stocks for drawdown from 365-day high...")
    output("=" * 70)

    stock_rows = [
        row for _, row in config.iterrows()
        if row['Ticker'] != 'CASH'
        and not row['Ticker'].endswith(' P')
        and not row['Ticker'].endswith(' C')
        and row.get('drawdown', 0) > 0
    ]
    total = len(stock_rows)
    if total == 0:
        output("No stocks with a drawdown threshold configured.")
        return []
    for row in stock_rows:
        output(f"  {row['Ticker']}: alert every {row['drawdown']:.0f}% drawdown")
    output(f"Found {total} stock(s) to scan.")
    output("")

    results = []

    for idx, row in enumerate(stock_rows, 1):
        ticker = row['Ticker']
        threshold = row['drawdown']
        scan_time = datetime.now().strftime('%H:%M:%S')
        output(f"[{scan_time}] ({idx}/{total}) {ticker}: Qualifying contract...")

        try:
            contract = Stock(ticker, 'SMART', 'USD')
            ib.qualifyContracts(contract)
            output(f"[{scan_time}] ({idx}/{total}) {ticker}: Requesting 1Y historical data...")
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='1 Y',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                timeout=60,
            )

            if not bars:
                output(f"[{scan_time}] ({idx}/{total}) {ticker}: No historical data available")
                continue

            output(f"[{scan_time}] ({idx}/{total}) {ticker}: Received {len(bars)} daily bars")

            high_365 = max(b.high for b in bars)
            current_price = bars[-1].close

            if high_365 <= 0:
                output(f"[{scan_time}] ({idx}/{total}) {ticker}: Invalid high price")
                continue

            drawdown_pct = ((high_365 - current_price) / high_365) * 100
            # Find which bucket this falls into based on per-ticker threshold
            bucket = int(drawdown_pct // threshold) * int(threshold)

            results.append({
                'Ticker': ticker,
                'High_365': high_365,
                'Current': current_price,
                'Drawdown_Pct': drawdown_pct,
                'Bucket': bucket,
                'Threshold': threshold,
            })

            output(f"[{scan_time}] ({idx}/{total}) {ticker}: 365-day High = ${high_365:,.2f} | "
                   f"Current = ${current_price:,.2f} | "
                   f"Drawdown = {drawdown_pct:.1f}%")

        except Exception as e:
            output(f"[{scan_time}] ({idx}/{total}) {ticker}: Error - {e}")

    output("")
    output("=" * 70)
    output("Drawdown Summary:")
    output("-" * 40)

    if not results:
        output("No stock data available for drawdown analysis.")
        return results

    # Group by per-ticker threshold buckets
    for r in results:
        t = int(r['Threshold'])
        b = r['Bucket']
        label = f"{b}%-{b + t}%"
        output(f"  {r['Ticker']} (threshold {t}%): bucket {label} | actual {r['Drawdown_Pct']:.1f}%")

    output("")
    # Highlight stocks that have crossed at least one threshold
    alerts = [r for r in results if r['Drawdown_Pct'] >= r['Threshold']]
    if alerts:
        output("Stocks exceeding their drawdown threshold:")
        for r in sorted(alerts, key=lambda x: -x['Drawdown_Pct']):
            crossed = int(r['Drawdown_Pct'] // r['Threshold'])
            output(f"  {r['Ticker']}: down {r['Drawdown_Pct']:.1f}% "
                   f"(crossed {crossed}x {int(r['Threshold'])}% threshold) "
                   f"from ${r['High_365']:,.2f} to ${r['Current']:,.2f}")
    else:
        output("No stocks have crossed their drawdown threshold.")

    return results
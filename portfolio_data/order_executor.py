"""
IBKR Order Executor – places rebalance trades via the Interactive Brokers API.

Buy  orders → Limit order at the current market price (from the rebalance plan).
Sell orders → Market order.

All orders use tif='DAY' and outsideRth=False so they:
  • remain pending when placed outside market hours,
  • become active at the next regular-session open, and
  • expire at that session's close (never carry forward).
"""

import logging
from ib_insync import Stock, MarketOrder, LimitOrder

logger = logging.getLogger(__name__)


def place_rebalance_orders(ib, trade_plan, output_callback=None):
    """
    Place orders for every actionable entry in *trade_plan*.

    Parameters
    ----------
    ib : ib_insync.IB
        A connected IB gateway / TWS instance.
    trade_plan : dict
        The dict returned by ``rabalance_portfolio()``.
        Expected keys per ticker: action, shares, market_price.
    output_callback : callable, optional
        Function called with status strings (defaults to ``print``).

    Returns
    -------
    list[ib_insync.Trade]
        A list of Trade objects returned by ``ib.placeOrder()``.
    """
    output = output_callback if output_callback is not None else print
    trades = []

    for ticker, info in trade_plan.items():
        if ticker == 'CASH':
            continue

        shares = int(info.get('shares', 0))
        action = info.get('action', '')
        market_price = info.get('market_price', 0)

        if shares <= 0 or action not in ('Buy', 'Sell'):
            continue

        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)

        if action == 'Buy':
            # Limit order at the current market price – DAY only
            order = LimitOrder('BUY', shares, round(market_price, 2))
            order.tif = 'DAY'
            order.outsideRth = False
            order_desc = f"LIMIT BUY {shares} x {ticker} @ ${market_price:.2f} [DAY]"
        else:
            # Market order for sells – DAY only
            order = MarketOrder('SELL', shares)
            order.tif = 'DAY'
            order.outsideRth = False
            order_desc = f"MARKET SELL {shares} x {ticker} [DAY]"

        try:
            trade = ib.placeOrder(contract, order)
            trades.append(trade)
            output(f"✓ Placed: {order_desc}")
            logger.info("Order placed – %s", order_desc)
        except Exception as exc:
            output(f"✗ Failed: {order_desc}  —  {exc}")
            logger.error("Order failed – %s: %s", order_desc, exc)

    if not trades:
        output("No orders to place.")
    else:
        output(f"\nTotal orders placed: {len(trades)}")

    return trades

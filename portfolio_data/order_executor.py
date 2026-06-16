"""
IBKR Order Executor – places rebalance trades via the Interactive Brokers API.

Regular rebalance:
  Buy  orders → Market order (placed immediately).
  Sell orders → Market order (placed immediately).

Drawdown rebalance:
  Buy  orders → Limit order at the drawdown threshold price.
  Sell orders → Market order, placed automatically when the first buy limit
                order fills.  If there are no buy orders, sells are placed
                immediately.

All orders use tif='DAY' and outsideRth=False so they:
  • remain pending when placed outside market hours,
  • become active at the next regular-session open, and
  • expire at that session's close (never carry forward).
"""

import logging
from ib_insync import Stock, MarketOrder, LimitOrder

logger = logging.getLogger(__name__)


def _place_sell_orders(ib, sell_items, output, trades):
    """Place all sell market orders immediately and append Trades to *trades*."""
    for ticker, info in sell_items:
        shares = int(info.get('shares', 0))
        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)
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


def place_rebalance_orders(ib, trade_plan, output_callback=None, is_drawdown=False):
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
    is_drawdown : bool, optional
        When True (drawdown rebalance), Buy orders are placed as Limit orders
        at the drawdown threshold price and Sell orders are triggered
        automatically when the first Buy limit order fills.
        When False (regular rebalance), all orders are placed as Market orders
        immediately.

    Returns
    -------
    list[ib_insync.Trade]
        A list of Trade objects returned by ``ib.placeOrder()``.
    """
    output = output_callback if output_callback is not None else print
    trades = []

    # Split trade plan into buys and sells
    buy_items = []
    sell_items = []
    for ticker, info in trade_plan.items():
        if ticker == 'CASH':
            continue
        shares = int(info.get('shares', 0))
        action = info.get('action', '')
        if shares <= 0 or action not in ('Buy', 'Sell'):
            continue
        if action == 'Buy':
            buy_items.append((ticker, info))
        else:
            sell_items.append((ticker, info))

    if is_drawdown:
        # ── Drawdown mode ────────────────────────────────────────────────────
        # Place all buy limit orders first.
        buy_order_ids = set()
        for ticker, info in buy_items:
            shares = int(info.get('shares', 0))
            market_price = info.get('market_price', 0)
            contract = Stock(ticker, 'SMART', 'USD')
            ib.qualifyContracts(contract)
            order = LimitOrder('BUY', shares, round(market_price, 2))
            order.tif = 'DAY'
            order.outsideRth = False
            order_desc = f"LIMIT BUY {shares} x {ticker} @ ${market_price:.2f} [DAY]"
            try:
                trade = ib.placeOrder(contract, order)
                buy_order_ids.add(trade.order.orderId)
                trades.append(trade)
                output(f"✓ Placed: {order_desc}")
                logger.info("Order placed – %s", order_desc)
            except Exception as exc:
                output(f"✗ Failed: {order_desc}  —  {exc}")
                logger.error("Order failed – %s: %s", order_desc, exc)

        if sell_items and buy_order_ids:
            # Register a fill handler: place sells when the first buy fills.
            sells_placed = [False]

            def on_fill(trade, fill):
                if sells_placed[0]:
                    return
                if trade.order.orderId not in buy_order_ids:
                    return
                sells_placed[0] = True
                ib.execDetailsEvent -= on_fill
                output(
                    f"\n✓ Buy filled ({trade.contract.symbol} @ "
                    f"${fill.execution.price:.2f}) – placing sell orders now..."
                )
                _place_sell_orders(ib, sell_items, output, trades)

            ib.execDetailsEvent += on_fill
            output("\nSell orders will be placed automatically when a buy order fills.")
        else:
            # No buys were placed (or no sells exist) – place sells immediately.
            _place_sell_orders(ib, sell_items, output, trades)

    else:
        # ── Regular rebalance: place all orders immediately ──────────────────
        for ticker, info in sell_items + buy_items:
            shares = int(info.get('shares', 0))
            action = info.get('action', '')
            contract = Stock(ticker, 'SMART', 'USD')
            ib.qualifyContracts(contract)
            if action == 'Buy':
                order = MarketOrder('BUY', shares)
                order_desc = f"MARKET BUY {shares} x {ticker} [DAY]"
            else:
                order = MarketOrder('SELL', shares)
                order_desc = f"MARKET SELL {shares} x {ticker} [DAY]"
            order.tif = 'DAY'
            order.outsideRth = False
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
        placed = len(trades)
        pending = " (sell orders pending fill)" if is_drawdown and sell_items and buy_order_ids else ""
        output(f"\nTotal orders placed: {placed}{pending}")

    return trades

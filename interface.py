import sys
import logging
import threading
import asyncio
import tkinter as tk
from io import StringIO

from portfolio_data.cal_portfolio import fetch_ibkr_portfolio, ibkr_conn, read_config, rabalance_portfolio, calculate_withdrawal, scan_drawdown
from portfolio_data.order_executor import place_rebalance_orders
from report import gen_report
from UI.ui_components import UIComponents
from portfolio_data.ratio_manager import RatioManager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Rebalancer")
        self.is_scanning = False
        self.is_drawdown_scanning = False
        self.refresh_interval = 5000
        self._last_rebalance_result = None
        self._last_rebalance_is_drawdown = False
        self._drawdown_scan_results = {}  # ticker -> high_365

        # Initialize IBKR connection and data
        self.ib = ibkr_conn()
        logging.info("Successfully connected to IBKR")
        self.config = read_config()
        logging.info("Portfolio configuration loaded successfully")
        self.current_position = fetch_ibkr_portfolio(self.ib)
        logging.info(f"Initial portfolio fetched - {len(self.current_position)} positions")

        # Initialize UI
        self.ui = UIComponents(root)
        self.ratio_mgr = RatioManager(self.ui, on_config_saved=self._reload_config)

        # Wire up button callbacks
        self.ui.rebalance_btn.config(command=self.rebalance)
        self.ui.scan_btn.config(command=self.start_scanning)
        self.ui.report_btn.config(command=self.gen_report)
        self.ui.stop_btn.config(command=self.stop_scanning)
        self.ui.place_orders_btn.config(command=self.place_orders)
        self.ui.withdraw_btn.config(command=self.withdraw_money)
        self.ui.drawdown_btn.config(command=self.drawdown_scan)
        self.ui.disconnect_btn.config(command=self.disconnect_ibkr)
    
        # Populate initial UI data
        self.ui.refresh_position(self.current_position)
        self.ui.refresh_ratio_table(self.config)
        logging.info("Portfolio Rebalancer application started")

    def start_scanning(self):
        if self.is_scanning:
            return
        logging.info("Starting portfolio scanning")
        self.is_scanning = True
        self.ui.append_output("\nStarted portfolio scanning. Fetching data...\n")
        self.refresh_current_positions()
        self.ui.show_stop_button()

    def stop_scanning(self):
        logging.info("Stopping portfolio scanning")
        self.is_scanning = False
        if self.is_drawdown_scanning:
            self._last_rebalance_result = None   # force re-rebalance in normal mode
            self._last_rebalance_is_drawdown = False
        self.is_drawdown_scanning = False
        self.ui.drawdown_btn.config(state='normal')
        self.ui.hide_stop_button()
        self.ui.append_output("\nStopped scanning.\n")
    
    def refresh_current_positions(self):
        if not self.is_scanning:
            return
        
        self.ui.append_output("Fetching latest positions...")
        
        def fetch_data():
            # Setup event loop for ib_insync in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                new_position = fetch_ibkr_portfolio(self.ib)
                self.root.after(0, lambda: self._update_ui_with_positions(new_position))
            except Exception as e:
                error_msg = f"\nError refreshing positions: {str(e)}"
                self.root.after(0, lambda: self.ui.append_output(error_msg))
                if self.is_scanning:
                    self.root.after(self.refresh_interval, self.refresh_current_positions)
            finally:
                loop.close()
        
        threading.Thread(target=fetch_data, daemon=True).start()
        
    def _update_ui_with_positions(self, new_position):
        """Update UI with fetched positions (runs on main thread)."""
        self.current_position = new_position
        self.ui.refresh_position(self.current_position)
        self.ui.append_output("\nPositions updated successfully")
        
        if self.is_scanning:
            self.root.after(self.refresh_interval, self.refresh_current_positions)

    def _apply_drawdown_adjustment(self, position):
        """Return a copy of the position DataFrame with CurrentValue and MarketPrice
        set to the drawdown threshold price: high_365 * (1 - threshold%).
        Falls back to current_price * (1 - threshold%) if scan data is unavailable."""
        adjusted = position.copy()
        for _, cfg_row in self.config.iterrows():
            ticker = cfg_row['Ticker']
            dd_pct = cfg_row.get('drawdown', 0)
            if dd_pct <= 0 or ticker == 'CASH':
                continue
            mask = adjusted['Ticker'] == ticker
            if mask.any():
                high_365 = self._drawdown_scan_results.get(ticker)
                if high_365 and high_365 > 0:
                    # Use the exact drawdown threshold price: 52-week high * (1 - threshold%)
                    threshold_price = high_365 * (1 - dd_pct / 100)
                    qty = adjusted.loc[mask, 'Quantity'].values[0]
                    adjusted.loc[mask, 'MarketPrice'] = threshold_price
                    adjusted.loc[mask, 'CurrentValue'] = qty * threshold_price
                else:
                    # Fallback when scan hasn't run yet
                    factor = 1 - dd_pct / 100
                    adjusted.loc[mask, 'CurrentValue'] = adjusted.loc[mask, 'CurrentValue'] * factor
                    adjusted.loc[mask, 'MarketPrice'] = adjusted.loc[mask, 'MarketPrice'] * factor
        return adjusted

    def rebalance(self):
        logging.info("Starting portfolio rebalance calculation")

        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
            logging.info(f"Rebalance calc: {msg}")

        if self.is_drawdown_scanning:
            gui_output("Drawdown mode active — simulating current values after drawdown:")
            for _, cfg_row in self.config.iterrows():
                dd_pct = cfg_row.get('drawdown', 0)
                if dd_pct > 0 and cfg_row['Ticker'] != 'CASH':
                    gui_output(f"  {cfg_row['Ticker']}: -{dd_pct:.0f}%")
            gui_output("")
            position = self._apply_drawdown_adjustment(self.current_position)
            # Use rebal_ratio_if_hit_dd as the Ratio for drawdown rebalancing
            dd_config = self.config.copy()
            if 'rebal_ratio_if_hit_dd' in dd_config.columns:
                dd_config['Ratio'] = dd_config['rebal_ratio_if_hit_dd']
                gui_output("Using drawdown rebalance ratios:")
                for _, r in dd_config.iterrows():
                    gui_output(f"  {r['Ticker']}: {r['Ratio']:.2%}")
                gui_output("")
        else:
            position = self.current_position
            dd_config = self.config

        result = rabalance_portfolio(dd_config, position, output_callback=gui_output)
        self._last_rebalance_result = result
        self._last_rebalance_is_drawdown = self.is_drawdown_scanning
        self.ui.show_output_lines(output_lines)
        self.ui.report_btn.config(state='normal' if result is not None else 'disabled')
        
        if result is None:
            logging.warning("Rebalance calculation failed - check ratio settings")

    def gen_report(self):
        # Use cached result or recalculate if needed
        if self._last_rebalance_result is None:
            output_lines = []
            result = rabalance_portfolio(
                self.config, 
                self.current_position,
                output_callback=lambda msg: output_lines.append(str(msg))
            )
            if result is None:
                self.ui.show_output_lines(output_lines)
                return
        else:
            result = self._last_rebalance_result

        # Capture report output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            gen_report.save_rebalance_to_excel(self.config)
            gen_report.save_performance_to_excel(result)
            report_output = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = old_stdout

        if report_output:
            self.ui.append_output(report_output + '\n')

    def withdraw_money(self):
        """Prompt user for withdrawal amount and calculate sells to maintain ratios."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Withdraw Money")
        dialog.geometry("420x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        bg, fg = '#1a1b2e', '#e2e4f0'
        accent, border = '#6366f1', '#2d2e4a'
        dialog.configure(bg=bg)

        # Center on parent window
        dialog.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 420) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        dialog.geometry(f"+{px}+{py}")

        tk.Label(dialog, text="Withdraw Money",
                 font=('Segoe UI', 14, 'bold'), bg=bg, fg=fg).pack(pady=(20, 6))
        tk.Label(dialog, text="Enter the amount to withdraw ($):",
                 font=('Segoe UI', 10), bg=bg, fg='#7a7d9c').pack(pady=(0, 10))

        entry = tk.Entry(dialog, font=('Segoe UI', 12), bg='#13141f', fg=fg,
                         insertbackground=fg, bd=0, relief='flat',
                         highlightbackground=border, highlightcolor=accent,
                         highlightthickness=1, justify='center')
        entry.pack(padx=50, fill='x', ipady=6)
        entry.focus_set()

        result = {'value': None}

        def submit(event=None):
            result['value'] = entry.get()
            dialog.destroy()

        entry.bind('<Return>', submit)

        btn_frame = tk.Frame(dialog, bg=bg)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Cancel", font=('Segoe UI', 9, 'bold'),
                  bg=border, fg=fg, bd=0, padx=20, pady=6, cursor='hand2',
                  activebackground='#3a3a50', activeforeground=fg,
                  command=dialog.destroy).pack(side='left', padx=8)
        tk.Button(btn_frame, text="Calculate", font=('Segoe UI', 9, 'bold'),
                  bg=accent, fg='#ffffff', bd=0, padx=20, pady=6, cursor='hand2',
                  activebackground='#4f46e5', activeforeground='#ffffff',
                  command=submit).pack(side='left', padx=8)

        dialog.wait_window()

        amount_str = result['value']
        if amount_str is None:
            return

        try:
            amount = float(amount_str.replace(',', '').strip())
        except ValueError:
            self.ui.show_output_lines(["Invalid amount entered. Please enter a numeric value."])
            return

        logging.info(f"Calculating withdrawal of ${amount:,.2f}")
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))

        result = calculate_withdrawal(self.config, self.current_position, amount, output_callback=gui_output)
        self.ui.show_output_lines(output_lines)

    # ── Place orders ────────────────────────────────────

    def place_orders(self):
        """Show a confirmation dialog with the rebalance trade plan, then place orders."""
        if self._last_rebalance_result is None:
            self.ui.append_output("\nPlease run Rebalance first before placing orders.\n")
            return

        trade_plan = self._last_rebalance_result

        # Build a human-readable summary of pending orders
        buy_lines = []
        sell_lines = []
        for ticker, info in trade_plan.items():
            if ticker == 'CASH':
                continue
            shares = int(info.get('shares', 0))
            action = info.get('action', '')
            price  = info.get('market_price', 0)
            if shares <= 0 or action not in ('Buy', 'Sell'):
                continue
            if action == 'Buy':
                if self._last_rebalance_is_drawdown:
                    buy_lines.append(f"  BUY  {shares:>5}  {ticker:<8}  LIMIT @ ${price:,.2f}  [DAY]")
                else:
                    buy_lines.append(f"  BUY  {shares:>5}  {ticker:<8}  MARKET  [DAY]")
            else:
                sell_lines.append(f"  SELL {shares:>5}  {ticker:<8}  MARKET  [DAY]")

        if not buy_lines and not sell_lines:
            self.ui.append_output("\nNo actionable orders in the current rebalance plan.\n")
            return

        buy_header = "── Buy (Limit) ──────────────────" if self._last_rebalance_is_drawdown else "── Buy (Market) ─────────────────"
        summary_parts = []
        if sell_lines:
            summary_parts.append("── Sell (Market) ─────────────────")
            summary_parts.extend(sell_lines)
        if buy_lines:
            summary_parts.append(buy_header)
            summary_parts.extend(buy_lines)
        summary_text = "\n".join(summary_parts)

        # ── Confirmation dialog ──
        dialog = tk.Toplevel(self.root)
        dialog.title("Confirm Orders")
        dialog.geometry("520x420")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        bg, fg = '#1a1b2e', '#e2e4f0'
        accent, border = '#6366f1', '#2d2e4a'
        danger = '#ef4444'
        dialog.configure(bg=bg)

        # Centre on parent
        dialog.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width()  - 520) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 420) // 2
        dialog.geometry(f"+{px}+{py}")

        tk.Label(dialog, text="⚠  Confirm Order Placement",
                 font=('Segoe UI', 14, 'bold'), bg=bg, fg='#f59e0b').pack(pady=(18, 4))
        tk.Label(dialog, text="The following DAY orders will be sent to IBKR:",
                 font=('Segoe UI', 10), bg=bg, fg='#7a7d9c').pack(pady=(0, 2))
        tk.Label(dialog, text="(Valid until the next market close only — will NOT carry forward)",
                 font=('Segoe UI', 8), bg=bg, fg='#7a7d9c').pack(pady=(0, 8))

        order_box = tk.Text(dialog, wrap='word', height=12,
                            bg='#13141f', fg=fg, font=('Consolas', 9),
                            bd=0, padx=10, pady=8, state='normal',
                            selectbackground=accent, selectforeground='#ffffff')
        order_box.insert('1.0', summary_text)
        order_box.config(state='disabled')
        order_box.pack(fill='x', padx=24, pady=(0, 6))

        tk.Label(dialog, text="Are you sure you want to place these orders?",
                 font=('Segoe UI', 10, 'bold'), bg=bg, fg=fg).pack(pady=(4, 10))

        confirmed = {'value': False}

        def on_confirm():
            confirmed['value'] = True
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg=bg)
        btn_frame.pack(pady=6)
        tk.Button(btn_frame, text="Cancel", font=('Segoe UI', 9, 'bold'),
                  bg=border, fg=fg, bd=0, padx=22, pady=6, cursor='hand2',
                  activebackground='#3a3a50', activeforeground=fg,
                  command=dialog.destroy).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Place Orders", font=('Segoe UI', 9, 'bold'),
                  bg=danger, fg='#ffffff', bd=0, padx=22, pady=6, cursor='hand2',
                  activebackground='#dc2626', activeforeground='#ffffff',
                  command=on_confirm).pack(side='left', padx=10)

        dialog.wait_window()

        if not confirmed['value']:
            self.ui.append_output("\nOrder placement cancelled by user.\n")
            return

        # Run on the main thread — ib_insync is not thread-safe.
        # placeOrder / qualifyContracts are fast (just send messages to TWS).
        self.ui.append_output("\nPlacing orders...\n")
        try:
            place_rebalance_orders(
                self.ib, trade_plan,
                output_callback=lambda msg: self.ui.append_output(msg + "\n"),
                is_drawdown=self._last_rebalance_is_drawdown
            )
        except Exception as exc:
            self.ui.append_output(f"Error placing orders: {exc}\n")

    def disconnect_ibkr(self):
        self.stop_scanning()
        if self.ib is not None:
            try:
                self.ib.disconnect()
                self.ib = None
                self.ui.append_output("\nDisconnected from IBKR.\n")
            except Exception as e:
                self.ui.append_output(f"\nError disconnecting from IBKR: {e}\n")
        else:
            self.ui.append_output("\nNo IBKR connection to disconnect.\n")

    def drawdown_scan(self):
        """Scan stocks for drawdown from their 365-day high, repeating every 60 seconds."""
        if self.is_drawdown_scanning:
            return
        logging.info("Starting drawdown scan")
        self.is_drawdown_scanning = True
        self._last_rebalance_result = None       # force re-rebalance in drawdown mode
        self._last_rebalance_is_drawdown = False
        self.ui.drawdown_btn.config(state='disabled')
        self.ui.show_output_lines(["Starting drawdown scan...\n"])
        self.ui.show_stop_button()
        self._run_drawdown_cycle()

    def stop_drawdown_scan(self):
        logging.info("Stopping drawdown scan")
        self.is_drawdown_scanning = False
        self._drawdown_scan_results = {}
        self.ui.drawdown_btn.config(state='normal')
        self.ui.append_output("\nDrawdown scanning stopped.\n")

    def _run_drawdown_cycle(self):
        if not self.is_drawdown_scanning:
            return

        def live_output(msg):
            self.ui.append_output(msg + "\n")
            self.root.update()

        try:
            scan_results = scan_drawdown(self.ib, self.config, output_callback=live_output)
            if scan_results:
                self._drawdown_scan_results = {r['Ticker']: r['High_365'] for r in scan_results}
        except Exception as e:
            error_msg = f"\nError during drawdown scan: {str(e)}"
            logging.error(error_msg)
            self.ui.append_output(error_msg)

        if self.is_drawdown_scanning:
            self.ui.append_output("\nNext scan in 60 seconds... (click Stop to cancel)\n")
            self.root.after(60000, self._run_drawdown_cycle)

    def _reload_config(self):
        try:
            self.config = read_config()
            self._last_rebalance_result = None
            self.ui.refresh_ratio_table(self.config)
            self.ui.append_output("Portfolio ratios saved and reloaded.\n")
        except Exception as e:
            self.ui.append_output(f"Failed to reload config: {e}\n")

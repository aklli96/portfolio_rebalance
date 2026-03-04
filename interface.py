import sys
import logging
import threading
import asyncio
from io import StringIO

from portfolio_data.cal_portfolio import fetch_ibkr_portfolio, ibkr_conn, read_config, rabalance_portfolio
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
        self.refresh_interval = 5000
        self._last_rebalance_result = None

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
        self.ui.hide_stop_button()
        self.ui.append_output("\nStopped portfolio scanning.\n")
    
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

    def rebalance(self):
        logging.info("Starting portfolio rebalance calculation")

        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
            logging.info(f"Rebalance calc: {msg}")

        result = rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        self._last_rebalance_result = result
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

    def _reload_config(self):
        try:
            self.config = read_config()
            self._last_rebalance_result = None
            self.ui.refresh_ratio_table(self.config)
            self.ui.append_output("Portfolio ratios saved and reloaded.\n")
        except Exception as e:
            self.ui.append_output(f"Failed to reload config: {e}\n")

from portfolio_data.cal_portfolio import fetch_ibkr_portfolio, ibkr_conn, read_config, rabalance_portfolio
from report import gen_report
from UI.ui_components import UIComponents
from portfolio_data.ratio_manager import RatioManager
from io import StringIO
import sys
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Rebalancer")

        # connection & data
        self.ib = ibkr_conn()
        logging.info("Successfully connected to IBKR")
        self.config = read_config()
        logging.info("Portfolio configuration loaded successfully")
        self.current_position = fetch_ibkr_portfolio(self.ib)
        logging.info(f"Initial portfolio fetched - {len(self.current_position)} positions")
        
        # last rebalance result, cached to avoid re-computation in gen_report
        self._last_rebalance_result = None

        # build UI
        self.ui = UIComponents(root)
        self.ratio_mgr = RatioManager(self.ui, on_config_saved=self._reload_config)

        # button wiring
        self.ui.rebalance_btn.config(command=self.rebalance)
        self.ui.scan_btn.config(command=self.start_scanning)
        self.ui.report_btn.config(command=self.gen_report)
        self.ui.stop_btn.config(command=self.stop_scanning)
        self.ui.disconnect_btn.config(command=self.disconnect_ibkr)
    
        # startup
        self.ui.refresh_position(self.current_position)
        self.ui.refresh_ratio_table(self.config)
        logging.info("Starting Portfolio Rebalancer application")

        # scanning state
        self.is_scanning = False
        self.refresh_interval = 5000  # 5 seconds

    def start_scanning(self):
        if self.is_scanning:
            return
        logging.info("Starting portfolio scanning")
        self.is_scanning = True
        self.refresh_current_positions()
        self.ui.show_stop_button()
        self.ui.append_output("\nStarted portfolio scanning. Click Stop to end.\n")

    def stop_scanning(self):
        logging.info("Stopping portfolio scanning")
        self.is_scanning = False
        self.ui.hide_stop_button()
        self.ui.append_output("\nStopped portfolio scanning.\n")
    
    def refresh_current_positions(self):
        if not self.is_scanning:
            return
        try:
            self.current_position = fetch_ibkr_portfolio(self.ib)
            self.ui.refresh_position(self.current_position)
            self.ui.append_output("\nPositions updated successfully")
        except Exception as e:
            self.ui.append_output(f"\nError refreshing positions: {str(e)}")
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
        # Use cached result if available, otherwise re-calculate
        if self._last_rebalance_result is None:
            output_lines = []
            result = rabalance_portfolio(self.config, self.current_position,
                                         output_callback=lambda msg: output_lines.append(str(msg)))
            if result is None:
                self.ui.show_output_lines(output_lines)
                return
        else:
            result = self._last_rebalance_result

        # Capture report print output
        mystdout = StringIO()
        old_stdout = sys.stdout
        sys.stdout = mystdout
        try:
            gen_report.save_rebalance_to_excel(self.config)
            gen_report.save_performance_to_excel(result)
        finally:
            sys.stdout = old_stdout

        report_output = mystdout.getvalue().strip()
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
            self._last_rebalance_result = None  # invalidate cache
            self.ui.refresh_ratio_table(self.config)
            self.ui.append_output("Portfolio ratios saved and reloaded.\n")
        except Exception as e:
            self.ui.append_output(f"Failed to reload config: {e}\n")

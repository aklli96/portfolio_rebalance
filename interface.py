from portfolio_data.cal_portfolio import fetch_ibkr_portfolio, ibkr_conn, read_config, rabalance_portfolio
from report import gen_report
from UI.ui_components import UIComponents
from portfolio_data.ratio_manager import RatioManager
from io import StringIO
import sys
import logging


# Configure logging to show in cmd
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
        
        # build UI
        self.ui = UIComponents(root)

        # wire ratio manager
        self.ratio_mgr = RatioManager(self.ui, on_config_saved=self._reload_config)

        # button wiring
        self.ui.rebalance_btn.config(command=self.rebalance)
        self.ui.scan_btn.config(command=self.start_scanning)  # New scan button
        self.ui.report_btn.config(command=self.gen_report)
        self.ui.stop_btn.config(command=self.stop_scanning)
        self.ui.disconnect_btn.config(command=self.disconnect_ibkr)
    
        # startup
        self._setup_connection_and_load()
        logging.info("Starting Portfolio Rebalancer application")

        #setup the scanner
        self.is_scanning = False
        self.refresh_interval = 5000  # 5 seconds

    def _setup_connection_and_load(self):
        # fetch initial portfolio (cal_portfolio returns CASH row)
        self.ui.refresh_position(self.current_position)
        logging.info(f"Initial portfolio fetched - {len(self.current_position)} positions")
        self.ui.refresh_ratio_table(self.config)

    def start_scanning(self):
        """Start continuous portfolio scanning"""
        if self.is_scanning:
            return
            
        logging.info("Starting portfolio scanning")
        self.is_scanning = True
        self.refresh_current_positions()
        self.ui.show_stop_button()
        self.ui.append_output("\nStarted portfolio scanning. Click Stop to end.\n")

    def stop_scanning(self):
        """Stop continuous portfolio scanning"""
        logging.info("Stopping portfolio scanning")
        self.is_scanning = False
        self.ui.hide_stop_button()
        self.ui.append_output("\nStopped portfolio scanning.\n")
    
    def refresh_current_positions(self):
        """Refresh current positions and schedule next update if scanning"""
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
        """Calculate rebalance without starting scan"""
        logging.info("Starting portfolio rebalance calculation")
        # Fetch latest snapshot for calculation


        # Run rebalance calculations
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
            logging.info(f"Rebalance calc: {msg}")

        result = rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        self.ui.show_output_lines(output_lines)
        self.ui.report_btn.config(state='normal' if result is not None else 'disabled')
        
        if result is None:
            logging.warning("Rebalance calculation failed - check ratio settings")


    def gen_report(self):
        # run rebalance to get result dict (non-destructive)
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        result = rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        if result is None:
            self.ui.show_output_lines(output_lines)
            return

        # generate reports
        mystdout = StringIO()
        old_stdout = sys.stdout
        sys.stdout = mystdout
        try:
            gen_report.save_rebalance_to_excel(self.config)
            gen_report.save_performance_to_excel(result)
        finally:
            sys.stdout = old_stdout

        report_output = mystdout.getvalue()
        output = '\n'.join(output_lines)
        if report_output:
            output = (output + '\n' if output else '') + report_output
        self.ui.append_output(output + '\n')

    def disconnect_ibkr(self):
        self.ui.stop_scanning()  # Add this line to stop scanning when disconnecting
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
            self.ui.refresh_ratio_table(self.config)
            self.ui.append_output("Portfolio ratios saved and reloaded.\n")
        except Exception as e:
            self.ui.append_output(f"Failed to reload config: {e}\n")

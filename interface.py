from portfolio_data.cal_portfolio import fetch_ibkr_portfolio, ibkr_conn, read_config, rabalance_portfolio
from report import gen_report
from UI.ui_components import UIComponents
from portfolio_data.scanner import Scanner
from portfolio_data.ratio_manager import RatioManager
from io import StringIO
import sys

class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Rebalancer")

        # connection & data
        self.ib = None
        self.config = None
        self.current_position = None

        # build UI
        self.ui = UIComponents(root)

        # wire ratio manager
        self.ratio_mgr = RatioManager(self.ui, on_config_saved=self._reload_config)

        # scanner (background) - fetcher expects (ib) argument
        self.scanner = Scanner(self.ui, fetcher=fetch_ibkr_portfolio)

        # button wiring
        self.ui.rebalance_btn.config(command=self.rebalance)
        self.ui.report_btn.config(command=self.gen_report)
        self.ui.stop_btn.config(command=self.scanner.stop)
        self.ui.disconnect_btn.config(command=self.disconnect_ibkr)

        # startup
        self._setup_connection_and_load()

    def _setup_connection_and_load(self):
        # connect to IB
        try:
            self.ib = ibkr_conn()
        except Exception as e:
            self.ui.append_output(f"IBKR connection failed: {e}\n")
            self.ib = None

        # load config
        try:
            self.config = read_config()
        except Exception as e:
            self.ui.append_output(f"Failed to read config: {e}\n")
            self.config = None

        # fetch initial portfolio (cal_portfolio returns CASH row)
        if self.ib is not None:
            try:
                self.current_position = fetch_ibkr_portfolio(self.ib)
                self.ui.refresh_position(self.current_position)
            except Exception as e:
                self.ui.append_output(f"Failed to fetch initial portfolio: {e}\n")
                self.current_position = None

        # refresh ratio table
        self.ui.refresh_ratio_table(self.config)

    def rebalance(self):
        # fetch latest synchronous snapshot and refresh UI
        if self.ib is not None:
            try:
                self.current_position = fetch_ibkr_portfolio(self.ib)
                self.ui.refresh_position(self.current_position)
            except Exception as e:
                self.ui.append_output(f"Failed to fetch latest portfolio before rebalance: {e}\n")

        # run rebalance calculations
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        result = rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        # show outputs in UI
        self.ui.show_output_lines(output_lines)

        # enable/disable report button
        self.ui.report_btn.config(state='normal' if result is not None else 'disabled')

        # if rebalance returned a plan, start background scanning (pass IB instance)
        if result is not None and self.ib is not None:
            self.scanner.start(self.ib)

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
        # stop scanner first
        self.scanner.stop()
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
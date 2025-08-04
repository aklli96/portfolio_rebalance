
import tkinter as tk
from tkinter import ttk, scrolledtext
import cal_portfolio
import gen_report
import sys


class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Rebalancer")

        # Load data
        self.config = cal_portfolio.read_config()
        self.current_position = cal_portfolio.fetch_ibkr_portfolio()

        # Table for positions (convert NaN to 0, hide MarketPrice)
        self.position_label = ttk.Label(root, text="Current Positions")
        self.position_label.pack()
        pos_df = self.current_position.fillna(0)
        if 'MarketPrice' in pos_df.columns:
            pos_df = pos_df.drop(columns=['MarketPrice'])
        self.position_tree = ttk.Treeview(root, columns=list(pos_df.columns), show='headings', height=8)
        for col in pos_df.columns:
            self.position_tree.heading(col, text=col)
            self.position_tree.column(col, width=100)
        for _, row in pos_df.iterrows():
            self.position_tree.insert('', 'end', values=list(row))
        self.position_tree.pack(padx=5, pady=5)

        # Table for ratio settings (format Ratio as percentage with 3 decimal places)
        self.ratio_label = ttk.Label(root, text="Ratio Settings")
        self.ratio_label.pack()
        ratio_df = self.config.copy()
        if 'Ratio' in ratio_df.columns:
            ratio_df['Ratio'] = ratio_df['Ratio'].apply(lambda x: f"{x:.3%}")
        self.ratio_tree = ttk.Treeview(root, columns=list(ratio_df.columns), show='headings', height=8)
        for col in ratio_df.columns:
            self.ratio_tree.heading(col, text=col)
            self.ratio_tree.column(col, width=100)
        for _, row in ratio_df.iterrows():
            self.ratio_tree.insert('', 'end', values=list(row))
        self.ratio_tree.pack(padx=5, pady=5)


        # Frame for buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)
        # Rebalance button
        self.rebalance_btn = ttk.Button(btn_frame, text="Rebalance", command=self.rebalance)
        self.rebalance_btn.pack(side=tk.LEFT, padx=5)
        # Gen report button
        self.report_btn = ttk.Button(btn_frame, text="Gen report", command=self.gen_report)
        self.report_btn.pack(side=tk.LEFT, padx=5)

        # Output text box
        self.output_box = scrolledtext.ScrolledText(root, width=80, height=12, state='disabled')
        self.output_box.pack(padx=5, pady=5)

    def rebalance(self):
        # Collect output via callback
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        cal_portfolio.rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        output = '\n'.join(output_lines)
        self.output_box.config(state='normal')
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, output)
        self.output_box.config(state='disabled')

    def gen_report(self):
        # Collect output via callback and capture print output from gen_report
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        result = cal_portfolio.rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        # Capture print output from gen_report
        try:
            gen_report.save_rebalance_to_excel(result, self.config)
        finally:
            sys.stdout = old_stdout
        report_output = mystdout.getvalue()
        output = '\n'.join(output_lines)
        if report_output:
            output += ('\n' if output else '') + report_output
        self.output_box.config(state='normal')
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, output)
        self.output_box.config(state='disabled')
from tkinter import ttk, scrolledtext
import tkinter as tk
import pandas as pd


class UIComponents:
    def __init__(self, root):
        self.root = root

        # positions
        self.position_label = ttk.Label(root, text="Current Positions")
        self.position_label.pack(padx=5, pady=(6,0))
        self.position_tree = ttk.Treeview(root, show='headings', height=8)
        self.position_tree.pack(padx=5, pady=5, fill='x')

        # ratios area (tree)
        self.ratio_label = ttk.Label(root, text="Ratio Settings")
        self.ratio_label.pack(padx=5, pady=(6,0))
        self.ratio_tree = ttk.Treeview(root, show='headings', height=8)
        self.ratio_tree.pack(padx=5, pady=5, fill='x')

        # buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=6)
        self.rebalance_btn = ttk.Button(btn_frame, text="Rebalance")
        self.rebalance_btn.pack(side=tk.LEFT, padx=4)
        self.scan_btn = ttk.Button(btn_frame, text="Start Scanning")
        self.scan_btn.pack(side=tk.LEFT, padx=4)
        self.report_btn = ttk.Button(btn_frame, text="Gen report")
        self.report_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop")
        self.stop_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn.pack_forget()  # Initially hidden
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect IBKR")
        self.disconnect_btn.pack(side=tk.LEFT, padx=4)

        # output
        self.output_box = scrolledtext.ScrolledText(root, width=90, height=12, state='disabled')
        self.output_box.pack(padx=5, pady=6, fill='both')

    # ── UI helpers ────────────────────────────────────────

    def refresh_position(self, df):
        """Update the position table with new data."""
        for item in self.position_tree.get_children():
            self.position_tree.delete(item)
        
        pos_df = df.fillna(0)
        if 'MarketPrice' in pos_df.columns:
            pos_df = pos_df.drop(columns=['MarketPrice'])
        
        cols = list(pos_df.columns)
        if list(self.position_tree['columns']) != cols:
            self.position_tree['columns'] = cols
            for col in cols:
                self.position_tree.heading(col, text=col)
                self.position_tree.column(col, width=120)

        for _, row in pos_df.iterrows():
            values = [f"{x:.2f}" if isinstance(x, float) else x for x in row]
            self.position_tree.insert('', 'end', values=values)

    def refresh_ratio_table(self, cfg):
        """Rebuild the ratio treeview from a config DataFrame."""
        if cfg is None or cfg.empty:
            df = pd.DataFrame(columns=['Ticker', 'Ratio'])
        else:
            df = cfg.copy()
            if 'Ratio' in df.columns:
                df['Ratio'] = df['Ratio'].apply(lambda x: f"{x:.3%}")

        cols = list(df.columns)
        # Always clear existing rows
        for item in self.ratio_tree.get_children():
            self.ratio_tree.delete(item)

        if list(self.ratio_tree['columns']) != cols:
            self.ratio_tree.config(columns=cols)
            for col in cols:
                self.ratio_tree.heading(col, text=col)
                self.ratio_tree.column(col, width=120)

        for _, row in df.iterrows():
            self.ratio_tree.insert('', 'end', values=list(row))

    def append_output(self, msg: str):
        self.output_box.config(state='normal')
        self.output_box.insert(tk.END, msg)
        self.output_box.see(tk.END)
        self.output_box.config(state='disabled')

    def show_output_lines(self, lines):
        self.output_box.config(state='normal')
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, '\n'.join(lines))
        self.output_box.config(state='disabled')

    def show_stop_button(self):
        self.stop_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn.config(state='normal')

    def hide_stop_button(self):
        self.stop_btn.config(state='disabled')
        self.stop_btn.pack_forget()
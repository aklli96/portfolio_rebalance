from tkinter import ttk, scrolledtext
import tkinter as tk
import pandas as pd
import threading
import asyncio
import time

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

        # buttons (created here so interface.py can wire commands)
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=6)
        self.rebalance_btn = ttk.Button(btn_frame, text="Rebalance")
        self.rebalance_btn.pack(side=tk.LEFT, padx=4)
        self.report_btn = ttk.Button(btn_frame, text="Gen report")
        self.report_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_scanning)
        # stop_btn not packed initially
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect IBKR")
        self.disconnect_btn.pack(side=tk.LEFT, padx=4)

        # output
        self.output_box = scrolledtext.ScrolledText(root, width=90, height=12, state='disabled')
        self.output_box.pack(padx=5, pady=6, fill='both')

        # scanning state (migrated scanner)
        self._scan_thread = None
        self._scan_stop_event = threading.Event()
        self._scan_ib = None
        self._scan_fetcher = None
        self._scan_interval = 5.0

    # UI helpers
    def refresh_position(self, df):

        # Prepare display: hide MarketPrice but keep CASH row and CurrentValue
        display_df = df.fillna(0).drop(columns=['MarketPrice'], errors='ignore')

        cols = list(display_df.columns)
        # reconfigure columns if changed
        if list(self.position_tree['columns']) != cols:
            for c in self.position_tree.get_children():
                self.position_tree.delete(c)
            self.position_tree.config(columns=cols)
            for col in cols:
                self.position_tree.heading(col, text=col)
                self.position_tree.column(col, width=120)
        else:
            # clear rows
            for item in self.position_tree.get_children():
                self.position_tree.delete(item)

        for _, row in display_df.iterrows():
            values = [("" if pd.isna(v) else v) for v in list(row)]
            self.position_tree.insert('', 'end', values=values)

    def refresh_ratio_table(self, cfg):
        if cfg is None or cfg.empty:
            df = pd.DataFrame(columns=['Ticker', 'Ratio'])
        else:
            df = cfg.copy()
            if 'Ratio' in df.columns:
                df['Ratio'] = df['Ratio'].apply(lambda x: f"{x:.3%}")
        cols = list(df.columns)
        if list(self.ratio_tree['columns']) != cols:
            for c in self.ratio_tree.get_children():
                self.ratio_tree.delete(c)
            self.ratio_tree.config(columns=cols)
            for col in cols:
                self.ratio_tree.heading(col, text=col)
                self.ratio_tree.column(col, width=120)
        else:
            for item in self.ratio_tree.get_children():
                self.ratio_tree.delete(item)
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
        try:
            self.stop_btn.pack(side=tk.LEFT, padx=4)
        except Exception:
            pass

    def hide_stop_button(self):
        try:
            self.stop_btn.pack_forget()
        except Exception:
            pass
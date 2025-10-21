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

        # buttons (created here so interface.py can wire commands)
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=6)
        self.rebalance_btn = ttk.Button(btn_frame, text="Rebalance")
        self.rebalance_btn.pack(side=tk.LEFT, padx=4)
        self.report_btn = ttk.Button(btn_frame, text="Gen report")
        self.report_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop")
        # stop_btn not packed initially
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect IBKR")
        self.disconnect_btn.pack(side=tk.LEFT, padx=4)

        # output
        self.output_box = scrolledtext.ScrolledText(root, width=90, height=12, state='disabled')
        self.output_box.pack(padx=5, pady=6, fill='both')

    # UI helpers
    def refresh_position(self, df):
        """
        Accepts:
         - pandas.DataFrame
         - tuple (df, cash_value)
         - dict convertible to DataFrame
        Ensures CASH row is preserved/added and CurrentValue computed.
        """
        cash_from_arg = None

        # Normalize input
        if df is None:
            df = pd.DataFrame()
        elif isinstance(df, tuple) and len(df) >= 2:
            maybe_df, maybe_cash = df[0], df[1]
            if isinstance(maybe_df, pd.DataFrame):
                df = maybe_df.copy()
                cash_from_arg = maybe_cash
        elif isinstance(df, dict):
            try:
                df = pd.DataFrame(df)
                # transpose if needed
                if 'Ticker' not in df.columns and 'Ticker' in df.index:
                    df = df.reset_index().rename(columns={'index': 'Ticker'})
            except Exception:
                df = pd.DataFrame()

        # ensure dataframe copy
        df = df.copy()

        # If index holds tickers, reset
        if 'Ticker' not in df.columns and df.index.name in (None, 'Ticker'):
            try:
                df = df.reset_index().rename(columns={'index': 'Ticker'})
            except Exception:
                pass

        # If a cash value provided separately, ensure CASH row exists
        if cash_from_arg is not None:
            try:
                cash_val = float(cash_from_arg)
            except Exception:
                cash_val = 0.0
            if not ('Ticker' in df.columns and 'CASH' in df['Ticker'].astype(str).values):
                cash_row = {'Ticker': 'CASH', 'Quantity': 0.0, 'AvgCost': 0.0,
                            'MarketPrice': 0.0, 'CurrentValue': round(cash_val, 2)}
                df = pd.concat([df, pd.DataFrame([cash_row])], ignore_index=True)

        # If there's an explicit cash column and no CASH row, add it
        if 'Ticker' in df.columns and 'CASH' not in df['Ticker'].astype(str).values:
            for c in ['Cash', 'CashBalance', 'AvailableFunds', 'TotalCash', 'CashValue']:
                if c in df.columns:
                    try:
                        cash_val = float(df[c].sum()) if df[c].dtype.kind in 'fi' else float(df[c].astype(float).sum())
                        cash_row = {'Ticker': 'CASH', 'Quantity': 0.0, 'AvgCost': 0.0,
                                    'MarketPrice': 0.0, 'CurrentValue': round(cash_val, 2)}
                        df = pd.concat([df, pd.DataFrame([cash_row])], ignore_index=True)
                    except Exception:
                        pass
                    break

        # Compute CurrentValue if possible
        if 'Quantity' in df.columns and 'MarketPrice' in df.columns:
            try:
                df['CurrentValue'] = (df['Quantity'].fillna(0).astype(float) *
                                      df['MarketPrice'].fillna(0).astype(float)).round(2)
            except Exception:
                pass

        # Ensure CASH row exists even if no special columns
        if 'Ticker' in df.columns and 'CASH' not in df['Ticker'].astype(str).values:
            # try to infer cash from Account columns if present; fallback to nothing
            pass  # nothing to add if none found

        # Prepare display: hide MarketPrice but keep CASH row and CurrentValue
        display_df = df.fillna('').drop(columns=['MarketPrice'], errors='ignore')

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
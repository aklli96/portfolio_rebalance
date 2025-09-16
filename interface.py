import tkinter as tk
from tkinter import ttk, scrolledtext
import cal_portfolio
import gen_report
import sys
import pandas as pd
from io import StringIO
from cal_portfolio import fetch_ibkr_portfolio


class PortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio Rebalancer")


        # Entry popup for editing ratios
        self.edit_popup = None
        self.edit_entry = None
        
        # Load data
        self.config = cal_portfolio.read_config()
        self.current_position, self.ib = fetch_ibkr_portfolio()

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

        # Table for ratio settings with editing capability
        ratio_frame = ttk.Frame(root)
        ratio_frame.pack(padx=5, pady=5)
        
        self.ratio_label = ttk.Label(ratio_frame, text="Ratio Settings")
        self.ratio_label.pack()
        
        # Create a frame for the table and validation message
        table_frame = ttk.Frame(ratio_frame)
        table_frame.pack(fill='x')
        
        # Table
        ratio_df = self.config.copy()
        if 'Ratio' in ratio_df.columns:
            ratio_df['Ratio'] = ratio_df['Ratio'].apply(lambda x: f"{x:.3%}")
        
        self.ratio_tree = ttk.Treeview(table_frame, columns=list(ratio_df.columns), show='headings', height=8)
        for col in ratio_df.columns:
            self.ratio_tree.heading(col, text=col)
            self.ratio_tree.column(col, width=100)
        
        for _, row in ratio_df.iterrows():
            self.ratio_tree.insert('', 'end', values=list(row))
        
        self.ratio_tree.pack(side='left')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.ratio_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.ratio_tree.configure(yscrollcommand=scrollbar.set)
        
        # Double-click to edit
        self.ratio_tree.bind('<Double-1>', self.edit_ratio)
        
        # Validation message label
        self.validation_label = ttk.Label(ratio_frame, text="", foreground="red")
        self.validation_label.pack()
        
        # Save button
        self.save_btn = ttk.Button(ratio_frame, text="Save Changes", command=self.save_ratios)
        self.save_btn.pack(pady=5)


        # Frame for buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)
        # Rebalance button
        self.rebalance_btn = ttk.Button(btn_frame, text="Rebalance", command=self.rebalance)
        self.rebalance_btn.pack(side=tk.LEFT, padx=5)
        # Gen report button
        self.report_btn = ttk.Button(btn_frame, text="Gen report", command=self.gen_report)
        self.report_btn.pack(side=tk.LEFT, padx=5)
        # Refresh button
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Current Value", command=self.refresh_current_value)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        # Disconnect button
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect IBKR", command=self.disconnect_ibkr)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

        # Output text box
        self.output_box = scrolledtext.ScrolledText(root, width=80, height=12, state='disabled')
        self.output_box.pack(padx=5, pady=5)

    def rebalance(self):
        # Collect output via callback
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        result = cal_portfolio.rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        output = '\n'.join(output_lines)
        self.output_box.config(state='normal')
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, output)
        self.output_box.config(state='disabled')
        
        # If validation failed, disable the gen_report button
        self.report_btn.config(state='disabled' if result is None else 'normal')
    

    def refresh_current_value(self):
        try:
            # Disconnect existing connection if any
            if self.ib is not None:
                self.ib.disconnect()
            
            # Fetch fresh data from IBKR
            self.current_position, self.ib = fetch_ibkr_portfolio()
            
            # Update the table
            pos_df = self.current_position.fillna(0)
            if 'MarketPrice' in pos_df.columns:
                pos_df = pos_df.drop(columns=['MarketPrice'])
            
            # Clear existing table
            for item in self.position_tree.get_children():
                self.position_tree.delete(item)
            
            # Repopulate with new data
            for _, row in pos_df.iterrows():
                self.position_tree.insert('', 'end', values=list(row))
            
            self.output_box.config(state='normal')
            self.output_box.insert(tk.END, "\nCurrent value refreshed successfully with latest data.\n")
            self.output_box.config(state='disabled')
        
        except Exception as e:
            self.output_box.config(state='normal')
            self.output_box.insert(tk.END, f"\nError refreshing data: {str(e)}\n")
            self.output_box.config(state='disabled')
    def disconnect_ibkr(self):
        """Disconnect from IBKR."""
        try:
            if self.ib is not None:
                self.ib.disconnect()
                self.ib = None
                self.output_box.config(state='normal')
                self.output_box.insert(tk.END, "\nDisconnected from IBKR.\n")
                self.output_box.config(state='disabled')
            else:
                self.output_box.config(state='normal')
                self.output_box.insert(tk.END, "\nNo IBKR connection to disconnect.\n")
                self.output_box.config(state='disabled')
        except Exception as e:
            self.output_box.config(state='normal')
            self.output_box.insert(tk.END, f"\nError disconnecting from IBKR: {e}\n")
            self.output_box.config(state='disabled')

    def gen_report(self):
        # Collect output via callback and capture print output from gen_report
        output_lines = []
        def gui_output(msg):
            output_lines.append(str(msg))
        result = cal_portfolio.rabalance_portfolio(self.config, self.current_position, output_callback=gui_output)
        
        if result is None:  # Validation failed
            self.output_box.config(state='normal')
            self.output_box.delete(1.0, tk.END)
            self.output_box.insert(tk.END, '\n'.join(output_lines))
            self.output_box.config(state='disabled')
            return
        
        # Capture print output from gen_report
        mystdout = StringIO()
        old_stdout = sys.stdout
        sys.stdout = mystdout
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
        
    def edit_ratio(self, event):
        """Handle double-click event to edit ratio"""
        # Get the item that was clicked
        item = self.ratio_tree.identify_row(event.y)
        column = self.ratio_tree.identify_column(event.x)
        
        # Only allow editing the Ratio column
        if column != '#2':  # Ratio is the second column
            return
            
        # Get the current value and position
        current_value = self.ratio_tree.item(item)['values'][1]
        x, y, w, h = self.ratio_tree.bbox(item, column)
        
        # Clean up any existing popup
        self.cancel_edit()
        
        # Create a frame for the entry
        self.edit_popup = ttk.Frame(self.ratio_tree)
        
        # Create entry widget
        self.edit_entry = ttk.Entry(self.edit_popup, width=15)
        self.edit_entry.insert(0, current_value.rstrip('%'))
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        
        # Bind events
        self.edit_entry.bind('<Return>', lambda e: self.save_edit(item))
        self.edit_entry.bind('<Escape>', lambda e: self.cancel_edit())
        
        # Show the popup
        self.edit_popup.place(x=x, y=y, width=w, height=h)
        self.edit_entry.pack(fill='both', expand=True)
    
    def save_edit(self, item):
        """Save the edited ratio value"""
        if self.edit_entry:
            try:
                # Get the new value and convert to float
                new_value = float(self.edit_entry.get().strip().rstrip('%')) / 100
                # Update the tree
                values = list(self.ratio_tree.item(item)['values'])
                values[1] = f"{new_value:.3%}"
                self.ratio_tree.item(item, values=values)
            except ValueError:
                # If the input is not a valid number, keep the old value
                pass
        self.cancel_edit()
        self.validate_ratios()
    
    def cancel_edit(self):
        """Cancel the editing and remove the popup"""
        if self.edit_popup:
            self.edit_popup.destroy()
            self.edit_popup = None
            self.edit_entry = None
    
    def validate_ratios(self):
        """Validate that ratios sum to 100%"""
        total = 0
        for item in self.ratio_tree.get_children():
            ratio_str = self.ratio_tree.item(item)['values'][1]
            ratio = float(ratio_str.rstrip('%')) / 100
            total += ratio
        
        if abs(total - 1.0) > 0.001:  # Allow for small floating point differences
            self.validation_label.config(text=f"Warning: Ratios sum to {total:.3%}, should be 100%")
            self.save_btn.config(state='disabled')
        else:
            self.validation_label.config(text="")
            self.save_btn.config(state='normal')
    
    def save_ratios(self):
        """Save the updated ratios to the CSV file"""
        # Update the config dataframe
        new_ratios = []
        for item in self.ratio_tree.get_children():
            values = self.ratio_tree.item(item)['values']
            ticker = values[0]
            ratio = float(values[1].rstrip('%')) / 100
            new_ratios.append({'Ticker': ticker, 'Ratio': ratio})
        
        new_df = pd.DataFrame(new_ratios)
        new_df['Ratio'] = new_df['Ratio'].apply(lambda x: f"{x:.2%}")
        new_df.to_csv('portfolio_setting.csv', index=False)
        
        # Reload the config
        self.config = cal_portfolio.read_config()
        
        # Show success message in output box
        self.output_box.config(state='normal')
        self.output_box.delete(1.0, tk.END)
        self.output_box.insert(tk.END, "Portfolio ratios saved successfully!")
        self.output_box.config(state='disabled')
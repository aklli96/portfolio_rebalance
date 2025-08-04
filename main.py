import gen_report, cal_portfolio, interface


if __name__ == "__main__":
    #config = cal_portfolio.read_config()
    #current_position = cal_portfolio.fetch_ibkr_portfolio()
    #result = cal_portfolio.rabalance_portfolio(config, current_position)
    #gen_report.save_rebalance_to_excel(result, config)
    root = interface.tk.Tk()
    app = interface.PortfolioApp(root)
    root.mainloop()
import gen_report, cal_port


if __name__ == "__main__":
    config = cal_port.read_config()
    current_position = cal_port.fetch_ibkr_portfolio()
    cal_port.rabalance_portfolio(config,current_position)

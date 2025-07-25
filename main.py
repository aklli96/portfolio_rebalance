import gen_report, cal_port


if __name__ == "__main__":
    config = cal_port.read_config()
    cal_port.rabalance_portfolio(config)


import pandas as pd
import sys
from ib_insync import IB

def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float)/100
    return config

def validation(config):
    if round(config['Ratio'].sum(),3) != 1:
        print(f"your portfolio ratio is not equal to 1, current ratio is {config['Ratio'].sum()}, please adjust the ratio until sum of the portfolio = 1")
        sys.exit()
    else:
        print("Validation passed")
        print("Calculating the gap between the existing amount and adjusted amount")

def fetch_ibkr_portfolio():
    ib = IB()
    # Connect to IB Gateway (default port is 4002, TWS is 7497)
    ib.connect('127.0.0.1', 4002, clientId=1)
    positions = ib.positions()
    # Convert positions to a DataFrame
    data = []
    for pos in positions:
        ticker = ib.reqMktData(pos.contract, '', False, False)
        ib.sleep(1)  # Give time for price to update
        data.append({
            'Ticker': pos.contract.symbol,
            'Quantity': pos.position,
            'AvgCost': pos.avgCost,
            'CurrentValue': pos.position * pos.avgCost
        })
    ib.disconnect()
    df = pd.DataFrame(data)
    return df

def rabalance_portfolio(config,current_position):
    validation(config)
    dict = {}
    amount_in_pool = current_position['CurrentValue'].sum()
    current_position = current_position[['Ticker', 'CurrentValue']]
    fetched_portfolio = config.merge(current_position, on='Ticker', how='left')
    fetched_portfolio.fillna(0, inplace=True)
    print("Depending on your ratio setting, please make the following adjustment in order to rebalance your porfolio:")
    for i in range(len(fetched_portfolio['Ratio'])):
        tb_changed_amt =  (amount_in_pool * fetched_portfolio['Ratio'][i]) - fetched_portfolio['CurrentValue'][i]
        if tb_changed_amt > 0:
            print(f"""Please put {tb_changed_amt} in to Ticker: {fetched_portfolio['Ticker'][i]}""")
        else:
            print(f"""Please withdraw {abs(tb_changed_amt)} from Ticker: {fetched_portfolio['Ticker'][i]}""")
        dict[fetched_portfolio['Ticker'][i]] = tb_changed_amt
    print(dict)
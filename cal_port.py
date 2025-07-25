import pandas as pd
import sys

def read_config():
    config = pd.read_csv('portfolio_setting.csv')
    config['Ratio'] = config['Ratio'].str.rstrip('%').astype(float)/100
    print(config['Ratio'])
    return config



def validation(config):
    if round(config['Ratio'].sum(),3) != 1:
        print(f"your portfolio ratio is not equal to 1, current ratio is {config['Ratio'].sum()}, please adjust the ratio until sum of the portfolio = 1")
        sys.exit()
    else:
        print("Validation passed")
        print("Calculating the gap between the existing amount and adjusted amount")


def rabalance_portfolio(config):
    validation(config)
    dict = {}
    amount_in_pool = config['current_value'].sum()
    print("Depending on your ratio setting, please make the following adjustment in order to rebalance your porfolio:")
    for i in range(len(config['Ratio'])):
        tb_changed_amt =  (amount_in_pool * config['Ratio'][i]) - config['current_value'][i] 
        if tb_changed_amt > 0:
            print(f"""Please put {tb_changed_amt} in to Ticker: {config['Ticker'][i]}""")
        else:
            print(f"""Please withdraw {abs(tb_changed_amt)} from Ticker: {config['Ticker'][i]}""")
        dict[config['Ticker'][i]] = tb_changed_amt
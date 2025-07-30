# portfolio_rebalance
Internal project - HF

This is the portfolio rebalancer, ensuring your position is aligning your ratio setting in [config file](https://github.com/aklli96/portfolio_rebalance/blob/main/portfolio_setting.csv)


## Pre-requite

Download and Install [IB gateway](https://www.interactivebrokers.com.hk/en/trading/ibgateway-latest.php)

Make the API enabled by reading the [TWS API Documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-introduction), please refer the section of TWS Settings

Create the virtual envirnoment for this application
```bash
python -m venv ib_position_rebalancer
```

Install the relevant python packages
```bash
pip install -r requirements.txt
```
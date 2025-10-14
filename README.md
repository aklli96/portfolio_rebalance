# portfolio_rebalance
Internal project - HF

This is the portfolio rebalancer, ensuring your position is aligning your ratio setting in [config file](https://github.com/aklli96/portfolio_rebalance/blob/main/portfolio_setting.csv)


## Prerequisite setup

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
Download the following [report template](https://github.com/user-attachments/files/22896820/portfolio_summary.xlsx), and place it into the same directorary as the main.py



## How to use this app
Portfolio rebalancing
1. Launch the IB gateway
2. Fill your preference in portfolio_setting.csv, please be reminded that the ticker name should same as the ticker name in IBKR
3. Run the program
```bash
python main.py
```

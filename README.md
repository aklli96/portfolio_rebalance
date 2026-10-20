# portfolio_rebalance
Internal project - HF

This is the portfolio rebalancer, ensuring your position is aligning your ratio setting in [portfolio_setting](https://github.com/user-attachments/files/22904827/portfolio_setting.csv)


## Prerequisite setup

Download and Install [IB gateway](https://www.interactivebrokers.com.hk/en/trading/ibgateway-latest.php)

Make the API enabled by reading the [TWS API Documentation](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-introduction), please refer the section "TWS Configuration For API Use" under TWS Settings

1. Disable “Read-Only API”
2. Change the "Socket Port" value to **4002**


Create the virtual envirnoment for this application
```bash
python -m venv ib_position_rebalancer
```

Install the relevant python packages
```bash
pip install -r requirements.txt
```
Download the following file and place it into the same directory as the main.py 

1. [portfolio_summary](https://github.com/user-attachments/files/22896820/portfolio_summary.xlsx)

Please directly put the portfolio_summary into the directory of portfolio_rebalance

2. [portfolio_setting](https://github.com/user-attachments/files/22904827/portfolio_setting.csv)

The ticker name refers to IBKR and the ratio is displaying with %, here is the example
|Ticker|Ratio|
|:---:|:---:|
|CASH|5%|
|QQQ|95%|

### Drawdown trigger (optional columns)

Two optional columns enable automatic rebalancing when a stock drops from its 365-day high:

| Column | Meaning |
|:---|:---|
| `drawdown` | Trigger threshold, e.g. `5%` — fires when the ticker drops 5% from its 365-day high. Leave empty to disable the trigger for that ticker. |
| `rebal_ratio_if_hit_dd` | The target ratio for **every** ticker to rebalance to once any trigger fires. |

Example — when VT drops 5% from its high, shift +5% into VT and -5% out of SGOV:

|Ticker|Ratio|drawdown|rebal_ratio_if_hit_dd|
|:---:|:---:|:---:|:---:|
|VT|26%|5%|31%|
|SGOV|70%||65%|

The `rebal_ratio_if_hit_dd` column must still sum to 100%.

**Drawdown Rebalance** button: one-shot calculation of what to buy/sell after a drop, no scanning required. Each ticker with a `drawdown` value is re-priced at its dropped price (52-week high × (1 − threshold) if the high is known from a prior scan, otherwise current price × (1 − threshold)) and the whole portfolio is rebalanced to the `rebal_ratio_if_hit_dd` ratios.

Example: VT 20% / SGOV 80% at $100 each; VT drops to $95 → target 25% / 75%, with the VT target calculated at $95. Confirm with **Place Orders** (in drawdown mode buys are placed as limit orders at the dropped price).


## How to use this app
Portfolio rebalancing
1. Launch the IB gateway
2. Fill your preference in portfolio_setting.csv, please be reminded that the ticker name should same as the ticker name in IBKR
3. Run the program
```bash
python main.py
```

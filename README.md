[![Hits](https://hits.seeyoufarm.com/api/count/incr/badge.svg?url=https%3A%2F%2Fgithub.com%2FHawtDogFlvrWtr%2Fcoinbase_bot%2F&count_bg=%2379C83D&title_bg=%23555555&icon=&icon_color=%23E7E7E7&title=hits&edge_flat=false)](https://hits.seeyoufarm.com)

# Coinbase Advanced Trading Bot

This bot buys and sells on Coinbase.com, using MACD/MACDs + RSI strategies to do so. The bot also allows you to set stoploss and take profit percentages that fire before signals do.



## Run The Bot

Clone the project

```bash
  git clone https://github.com/HawtDogFlvrWtr/coinbase_bot.git
```

Go to the project directory

```bash
  cd coinbase_bot
```

Install dependencies

```bash
  pip3 install pillow websocket-client telebot tinydb prettytable pandas_ta pandas ccxt

```

Rename the example config and add your settings. We recommend leaving everything under bot-config alone for now

```bash
  mv config.cfg_example config.cfg
```

Start the app with default settings

```bash
  # If you want to make real buys and sells
  python3 coinbase_bot.py

  # If you just want to play along with fake money
  python3 coinbase_bot_nobuy.py
```

Start the app with custom database or config

```bash
usage: coinbase_bot.py [-h] [-o ORDERS_FILE] [-c CONFIG_FILE]

options:
  -h, --help            show this help message and exit
  -o ORDERS_FILE, --orders_file ORDERS_FILE
                        The json filename for the orders file
  -c CONFIG_FILE, --config_file CONFIG_FILE
                        The json filename for the orders file
```


## Running Backtests

The backtester doesn't use your config file for anything but your api information, so you can run it without making changes to your config file.

```bash
  # Create backtesting data folder
  mkdir backtesting_data

  # Download the historical data for your symbols. You can/should make this run hourly via cron (0 * * * *) so you always have the latest backtesting data available
  python3 download_backtest_data.py

  # Start the backtester
  python3 coinbase_bot_backtester.py
```
Backtesting defaults to Jan 1 2023 (1672534800) onward, but can bet set with the -s setting parameter. The value should be in epoch [https://www.epochconverter.com/]. Backtesting can take a very long time, but i'm hoping to improve performance in the future. The more data you backtest, the longer it will take, obviously.

```bash
usage: coinbase_bot_backtester.py [-h] [-o ORDERS_FILE] [-c CONFIG_FILE] [-s START_TIME] [-rb RSI_BUY_LT] [-rs RSI_SELL_GT] [-t TAKE_PROFIT] [-sl STOPLOSS_PERCENT]

options:
  -h, --help            show this help message and exit
  -o ORDERS_FILE, --orders_file ORDERS_FILE
                        The json filename for the orders file
  -c CONFIG_FILE, --config_file CONFIG_FILE
                        The json filename for the orders file
  -s START_TIME, --start_time START_TIME
                        The start time for backtesting
  -rb RSI_BUY_LT, --rsi_buy_lt RSI_BUY_LT
                        The start time for backtesting
  -rs RSI_SELL_GT, --rsi_sell_gt RSI_SELL_GT
                        The start time for backtesting
  -t TAKE_PROFIT, --take_profit TAKE_PROFIT
                        The start time for backtesting
  -sl STOPLOSS_PERCENT, --stoploss_percent STOPLOSS_PERCENT
                        The start time for backtesting
```

## Backtesting Results from 1-1-2023 until 11-21-2023
```
["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD"]
TakeProfit 5%,  Stoploss -10%, RSI 50/50, Profit:  372.20%
TakeProfit 30%, Stoploss -30%, RSI 50/50, Profit:  639.13%
TakeProfit 10%, Stoploss -10%, RSI 50/50, Profit:  690.05%
TakeProfit 20%, Stoploss -20%, RSI 50/50, Profit:  702.70%
TakeProfit 5%,  Stoploss -20%, RSI 50/50, Profit:  833.17%
TakeProfit 10%, Stoploss -20%, RSI 50/50, Profit: 1002.87%

["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD","LTC/USD","AAVE/USD","RNDR/USD","MATIC/USD"]
TakeProfit 30%, Stoploss -30%, RSI 50/50, Profit  467.03%
TakeProfit 5%,  Stoploss -10%, RSI 50/50, Profit  573.57%
TakeProfit 20%, Stoploss -20%, RSI 50/50, Profit  621.81%
TakeProfit 5%,  Stoploss -20%, RSI 50/50, Profit  810.63%
TakeProfit 10%, Stoploss -10%, RSI 50/50, Profit  824.84%
TakeProfit 10%, Stoploss -20%, RSI 50/50, Profit 1149.07%
```

## Backtesting Results from 5-1-2016 until 11-21-2023
```
["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD"]
TakeProfit 5%,  Stoploss -10%, RSI 50/50, Profit:  333.83%
TakeProfit 5%,  Stoploss -20%, RSI 50/50, Profit: 1446.09%
TakeProfit 10%, Stoploss -10%, RSI 50/50, Profit: 2715.34%
TakeProfit 10%, Stoploss -20%, RSI 50/50, Profit: 3205.16%
TakeProfit 20%, Stoploss -20%, RSI 50/50, Profit: 4342.37%
TakeProfit 30%, Stoploss -30%, RSI 50/50, Profit: 5703.09%

["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD","LTC/USD","AAVE/USD","RNDR/USD","MATIC/USD"]
TakeProfit  5%, Stoploss -10%, RSI 50/50, Profit  501.35%
TakeProfit  5%, Stoploss -20%, RSI 50/50, Profit 1119.57%
TakeProfit 10%, Stoploss -10%, RSI 50/50, Profit 2398.47%
TakeProfit 10%, Stoploss -20%, RSI 50/50, Profit 3192.45%
TakeProfit 20%, Stoploss -20%, RSI 50/50, Profit 4022.58%
TakeProfit 30%, Stoploss -30%, RSI 50/50, Profit 5894.29%
```

## Support

I have made every attempt to ensure the accuracy and reliability of this application. However, this application is provided "as is" without warranty or support of any kind. I do not accept any  responsibility or liability for the accuracy, content, completeness, legality, or reliability of this application. Donations are welcome but doing so does not provide you support for this project.

- BTC Wallet: 3CyQ5LW9Ycuuu8Ddr5de5goWRh95C4rN8E
- ETH Wallet: 0x7eBEe95Af86Ed7f4B0eD29A322F1b811AD61DF36
- SHIB Wallet: 0x8cCc65a7786Bd5bf74E884712FF55C63b36B0112

Use this application at your own risk.

## Acknowledgements

 - [Learning about MACD+RSI](https://www.valutrades.com/en/blog/how-to-use-macd-and-rsi-together-to-spot-buying-opportunities)
 - [CCXT Documentation](https://docs.ccxt.com/#/)
 - [Telebot Documentation](https://pytba.readthedocs.io/en/latest/)
 - [Coinbase Advanced Trading API](https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome)

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

## Moving my bot to a new system

To transfer your bot to a new system, git clone to the new server following the instructions above, turn it off on the original bot, copy the config.cfg and ccb_database.json (Or whatever you set it to) file to the new system, and restart the bot on the new machine.

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
## Backtesting Results from 12-31-2022 until 11-29-2023
```
["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD"]
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,   Profit 13.43%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,   Profit 22.12%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,    Profit 28.2%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,   Profit 40.29%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,   Profit 84.45%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70,   Profit 115.6%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,   Profit 377.4%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,  Profit 384.33%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,  Profit 583.81%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,  Profit 594.23%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,  Profit 600.46%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50,  Profit 717.56%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0,  Profit 764.15%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0,  Profit 784.16%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0,  Profit 819.62%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 1006.13%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 1024.84%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 1052.17%

["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD","LTC/USD","AAVE/USD","RNDR/USD","MATIC/USD"]
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit   -100%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit -13.01%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit   16.3%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit   85.9%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit -25.57%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit -71.31%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 370.14%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 408.93%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 435.58%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 537.51%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 582.15%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 610.31%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 624.76%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 647.48%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 727.54%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 779.73%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 826.16%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 886.59%
```

## Backtesting Results from 04-30-2016 until 11-29-2023
```
["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD"]
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit    -100%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit  -51.07%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit  -48.57%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    7.31%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 2290.38%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 3125.52%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 3822.23%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 4035.99%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 4322.53%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 5615.27%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 6583.77%

["BTC/USD","ETH/USD","SOL/USD","LINK/USD","DOGE/USD","XRP/USD","AVAX/USD","LTC/USD","AAVE/USD","RNDR/USD","MATIC/USD"]
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit    -100%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-30/S-70, Profit    -100%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 1916.43%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 2616.51%
TakeProfit  5%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 2631.80%
TakeProfit  5%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 2980.48%
TakeProfit 10%, Stoploss -10%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 3923.17%
TakeProfit 10%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 4159.89%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 4209.25%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-50/S-50, Profit 5583.36%
TakeProfit 20%, Stoploss -20%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 5928.61%
TakeProfit 30%, Stoploss -30%, Buy Percent 10%, Spend Dollars 2000, Duplicates True, Buy Higher True, RSI B-100/S-0, Profit 7329.58%
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

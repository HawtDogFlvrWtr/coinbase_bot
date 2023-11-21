import argparse
import configparser
import datetime
import hashlib
import hmac
import json
import os
import sys
import ccxt
import pandas as pd
import pandas_ta as ta
import time
from prettytable import PrettyTable
from tinydb import TinyDB, Query
from threading import Thread
from websocket import create_connection, WebSocketConnectionClosedException # websocket-client


parser = argparse.ArgumentParser()
parser.add_argument('-o', '--orders_file', help="The json filename for the orders file", default='coinbase_bot_bt.json')
parser.add_argument('-c', '--config_file', help="The json filename for the orders file", default='config.cfg')
parser.add_argument('-s', '--start_time', help="The start time for backtesting", type=int, default=1672531200)
parser.add_argument('-rb', '--rsi_buy_lt', help="The start time for backtesting", type=int, default=50)
parser.add_argument('-rs', '--rsi_sell_gt', help="The start time for backtesting", type=int, default=50)
parser.add_argument('-t', '--take_profit', help="The start time for backtesting", type=int, default=5)
parser.add_argument('-sl', '--stoploss_percent', help="The start time for backtesting", type=int, default=10)

args = parser.parse_args()
orders_json_filename = args.orders_file
config_file = args.config_file
since_start = args.start_time
rsi_buy_lt = args.rsi_buy_lt
rsi_sell_gt = args.rsi_sell_gt
take_profit = args.take_profit
stoploss_percent = -abs(args.stoploss_percent)
sleep_lookup = {'1m': 60, '1h': 3600, '1d': 86400} # Added second to give the exchange time to update the candles
overall_df = {}

config = configparser.ConfigParser()
config.read(config_file)
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')
timeframe = config.get('bot-config', 'timeframe')
spend_dollars = int(config.get('spend-config', 'spend_dollars'))
buy_percent = int(config.get('spend-config', 'buy_percent'))
symbols = json.loads(config.get('bot-config', 'symbols'))
buy_when_higher = config.get('bot-config', 'buy_when_higher')


allow_duplicates = config.get('spend-config', 'allow_duplicates')
current_prices = {}

max_order_amount = buy_percent / 100 * spend_dollars
max_orders = int(spend_dollars / max_order_amount)

db = TinyDB(orders_json_filename, indent=4)
db.truncate() # Blow away old backtesting data
Orders = Query()

# Initialize the exchange and API keys
exchange = ccxt.coinbase ()
exchange_id = 'coinbase'
exchange_class = getattr(ccxt, exchange_id)
exchange = exchange_class({
    'apiKey': api_key,
    'secret': secret,
    'options':  {
        'fetchTicker': 'fetchTickerV3',
        'fetchTickers': 'fetchTickersV3',
        'fetchMarkets': 'fetchMarketsV3',
        'advanced': True
    },
    'enableRateLimit': True,
})

def insert_order(status, symbol, buy_amount, buy_time, signal_time, buy_price):
    db.insert({'symbol': symbol, 'status': status, 'buy_amount': buy_amount, 'buy_time': buy_time, 'signal_time': signal_time, 'buy_price': buy_price, 'sell_price': 0, 'sell_profit': 0, 'sell_time': 0})

def update_order(timestamp, sell_price, sell_profit, sell_time):
    db.update({'status': 'closed', 'sell_price': sell_price, 'sell_profit': sell_profit, 'sell_time': sell_time}, Orders.buy_time == timestamp)

def search_open_order(symbol):
    results = db.search((Orders.symbol == symbol) & (Orders.status == 'open'))
    if len(results) > 0:
        return True
    else:
        return False
    
def last_order_buy_price(symbol):
    od = sorted(db.search((Orders.symbol == symbol) & (Orders.status == 'open')), key=lambda k: k['buy_time'])
    if not od:
        return False
    else:
        return od[-1]['buy_price']
    
def open_order_count(symbol = None):
    if not symbol:
        return db.count((Orders.status == 'open'))
    else:
        return db.count((Orders.symbol == symbol) & (Orders.status == 'open'))
    
def search_open_duplicate_timestamp(symbol, timestamp):
    results = db.search((Orders.symbol == symbol) & (Orders.signal_time == timestamp) & (Orders.status == 'open'))
    if len(results) > 0:
        return True
    else:
        return False
    
def search_order(symbol):
    results = db.search(Orders.symbol == symbol)
    return results

def return_open_orders():
    results = db.search(Orders.status == 'open')
    return results

def return_closed_profit():
    results = db.all()
    profit_list = []
    for res in results:
            profit_list.append(res['sell_profit'])
    return sum(profit_list)

def fetch_ohlcv_data():
    global since_start
    global overall_df
    for symbol in symbols:
        file_path = "backtesting_data/%s_%s.json" % (symbol.replace('/', '-'), timeframe)
        if os.path.isfile(file_path):
            open_json = open(file_path)
            ohlcv_data = json.load(open_json)
            for i in range(len(ohlcv_data)):
                if ohlcv_data[i][0] / 1000 < since_start - 172800: # backtrack start time - 2 days to make sure we can calculate good macd/rsi info
                    continue
                else:
                    ohlcv_data = ohlcv_data[i:]
                    break
            print("Finding start data forwarder for %s at index %s in our historical data" % (symbol, i))

        else:
            print("Missing %s_%s.json please run downloader to make sure we have everything we need to run." % (symbol.replace('/', '-'), timeframe))
            sys.exit(1)
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        fast = 12
        slow = 26
        signal = 9
        macd = df.ta.macd(fast=fast, slow=slow, signal=signal)
        df = pd.concat([df, macd], axis=1)
        df = pd.concat([df, df.ta.rsi()], axis=1)
        overall_df[symbol] = df

def calculate_sma(df, period):
    return df['close'].rolling(window=period).mean()

def main():
    global since_start
    profit_list = []
    last_profit = 0
    take_profit_count = 0
    stoploss = 0
    sold = 0
    buy = 0
    fetch_ohlcv_data()
    last_timestamp = time.time() # In case nothing comes through, we set this to now.
    last_last_timestamp = 0
    while True:
        time_readable = datetime.datetime.fromtimestamp(since_start).strftime('%m-%d-%Y %H:%M:%S')
        for symbol in symbols:
            df = overall_df[symbol]
            index = 0
            for row in df.itertuples(): # Uh this is faster :D
                record_timestamp = row.timestamp / 1000
                if record_timestamp != since_start:
                    continue
                prev_index = index - 1
                macd = row.MACD_12_26_9
                macd_last = df['MACD_12_26_9'].iloc[prev_index]
                signal = row.MACDs_12_26_9
                signal_last = df['MACDs_12_26_9'].iloc[prev_index]
                close = row.close
                rsi = row.RSI_14
                last_timestamp = record_timestamp
                note_timestamp = datetime.datetime.fromtimestamp(record_timestamp).strftime('%m-%d-%Y %H:%M:%S')
                current_price = close
                index += 1
                # Buy Good Risk
                #print("Symbol: %s MACD: %s MACDs %s LMACD: %s LMACDs %s RSI: %s" % (symbol, macd, signal, macd_last, signal_last, rsi))
                if macd > signal and macd_last < signal_last and rsi <= rsi_buy_lt:
                    # Prevent duplicate coin
                    if allow_duplicates == 'False' and open_order_count(symbol) > 0: # Prevent duplicate coin
                        #print('%s - Skipping buy of symbol %s because we already have an open order' % (note_timestamp, symbol))
                        continue
                    if open_order_count() >= max_orders: # Already met our max open orders
                        #print('%s - Skipping buy of symbol %s because we are at our max orders.' % (note_timestamp, symbol))
                        continue
                    if buy_when_higher == 'False' and last_order_buy_price(symbol) > current_price: # Don't buy if we paid more for the last order
                        #print('%s - Skipping buy of symbol %s because a previous buy was at a lower price.' % (note_timestamp, symbol))
                        continue
                    # DO BUY
                    buy_amount = max_order_amount / current_price
                    buy_time = last_timestamp
                    buy += 1
                    print('%s - Buying %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
                    insert_order('open', symbol, buy_amount, buy_time, last_timestamp, current_price)
                # Sell Good Risk
                elif macd < signal and macd_last > signal_last and rsi >= rsi_sell_gt:
                    # DO SELL
                    if not search_open_order(symbol):
                        continue
                    buy_orders = search_order(symbol)
                    for buy_order in buy_orders:
                        if buy_order['status'] == 'closed':
                            continue
                        timestamp = buy_order['buy_time']
                        buy_price = buy_order['buy_price']
                        buy_amount = buy_order['buy_amount']
                        profit = round(((current_price - buy_price) / buy_price) * 100, 2)
                        if profit < 0.5:
                            continue
                        profit_list.append(profit)
                        sold += 1
                        print('%s - Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                        update_order(timestamp, current_price, profit, last_timestamp)
                buy_orders = search_order(symbol)
                for buy_order in buy_orders:
                    if buy_order['status'] == 'closed':
                        continue
                    timestamp = buy_order['buy_time']
                    buy_price = buy_order['buy_price']
                    buy_amount = buy_order['buy_amount']
                    profit = round(((current_price - buy_price) / buy_price) * 100, 2)
    
                    if profit <= stoploss_percent:
                        profit_list.append(profit)
                        stoploss += 1
                        print('%s - STOPLOSS Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                        update_order(timestamp, current_price, profit, last_timestamp)
                    elif profit >= take_profit:
                        profit_list.append(profit)
                        take_profit_count += 1
                        print('%s - TAKEPROFIT Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                        update_order(timestamp, current_price, profit, last_timestamp)
                if last_profit != sum(profit_list):
                    print("Profit on %s: %s%%" % (time_readable, round(sum(profit_list), 2)))
                    last_profit = sum(profit_list)
        since_start = int(since_start + sleep_lookup[timeframe])
        if since_start > time.time():
            print("Backtesting finished")
            print("Profit on %s: %s%%" % (time_readable, round(sum(profit_list), 2)))
            sys.exit(0)
        else:
            last_last_timestamp = since_start

if __name__ == "__main__":
    main()


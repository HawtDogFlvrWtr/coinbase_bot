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
parser.add_argument('-o', '--orders_file', help="The json filename for the orders file", default='coinbase_bot.json')
parser.add_argument('-c', '--config_file', help="The json filename for the orders file", default='config.cfg')

args = parser.parse_args()
orders_json_filename = args.orders_file
config_file = args.config_file
sleep_lookup = {'1m': 120, '1h': 3660, '1d': 86460} # Added second to give the exchange time to update the candles


config = configparser.ConfigParser()
config.read(config_file)
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')
risk_level = config.get('bot-config', 'risk_level')
timeframe = config.get('bot-config', 'timeframe')
spend_dollars = int(config.get('spend-config', 'spend_dollars'))
buy_percent = int(config.get('spend-config', 'buy_percent'))
symbols = json.loads(config.get('bot-config', 'symbols'))
allow_duplicates = config.get('spend-config', 'allow_duplicates')
current_prices = {}
ws_status = False

max_order_amount = buy_percent / 100 * spend_dollars
max_orders = int(spend_dollars / max_order_amount)

if risk_level == 'safe':
    print("Running the bot in SMA signal mode")
else:
    print("Running the bot in MACD/MACs + RSI mode")

db = TinyDB(orders_json_filename)
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

# Configuration
fast_sma_period = 10
slow_sma_period = 20

def ws_daemon():
    global current_prices
    global api_key
    global secret
    global ws
    global symbols
    global ws_status
    channel = "ticker"
    timestamp = str(int(time.time()))
    product_ids = []
    for symbol in symbols:
        product_ids.append(symbol.replace("/", '-'))
    product_ids_str = ",".join(product_ids)
    while True:
        ws_status = False
        message = f"{timestamp}{channel}{product_ids_str}"
        signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()

        ws = create_connection("wss://advanced-trade-ws.coinbase.com")
        ws.send(
            json.dumps(
                {
                    "type": "subscribe",
                    "product_ids": product_ids,
                    "channel": channel,
                    "api_key": api_key,
                    "timestamp": timestamp,
                    "signature": signature,
                }
            )
        )
        while ws.connected:
            ws_status = True
            data = ws.recv()
            if data != "":
                msg = json.loads(data)
                if 'events' not in msg: # Because why not, Coinbase
                    continue
                for event in msg['events']:
                    if 'tickers' not in event:
                        continue
                    for ticker in event['tickers']:
                        timestamp = time.time()
                        current_prices[ticker['product_id']] = {'price': float(ticker['price']), 'timestamp': timestamp}
                        for coin in current_prices: # Got an update from another coin so WS is still up. lets push the timestamp to everyone.
                            current_prices[coin]['timestamp'] = timestamp

# Start websocket thread
worker = Thread(target=ws_daemon, args=())
worker.daemon = True
worker.start()

def insert_order(status, symbol, buy_amount, buy_time, signal_time, buy_price):
    db.insert({'symbol': symbol, 'status': status, 'buy_amount': buy_amount, 'buy_time': buy_time, 'signal_time': signal_time, 'buy_price': buy_price, 'sell_price': "", 'sell_delta': "", 'sell_profit': "", 'sell_time': ""})

def update_order(id, sell_price, sell_delta, sell_profit, sell_time):
    db.update({'status': 'closed', 'sell_price': sell_price, 'sell_delta': sell_delta, 'sell_profit': sell_profit, 'sell_time': sell_time}, doc_id=id)

def search_open_order(symbol):
    results = db.search(Orders.symbol == symbol)
    if len(results) > 0:
        return True
    else:
        return False
    
def last_order_buy_price(symbol):
    od = sorted(db.search((Orders.symbol == symbol)), key=lambda k: k['buy_time'])
    if not od:
        return False
    else:
        return od[-1]['buy_price']
    
def open_order_count(symbol = None):
    if not symbol:
        return len(db)
    else:
        return db.count(Orders.symbol == symbol)
    
def search_open_duplicate_timestamp(symbol, timestamp):
    results = db.search((Orders.symbol == symbol) & (Orders.signal_time == timestamp))
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
    results = db.search(Orders.status == 'closed')
    profit_list = []
    for res in results:
        profit_list.append(res['sell_profit'])
    return sum(profit_list)

def fetch_ohlcv_data(symbol):
    ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe)
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def macd_signals(df, symbol):
    fast = 12
    slow = 26
    signal = 9
    macd = df.ta.macd(fast=fast, slow=slow, signal=signal)
    df = pd.concat([df, macd], axis=1)
    df = pd.concat([df, df.ta.rsi()], axis=1)
    return df

def print_orders(last_run):
    global current_prices
    global ws_status
    t = PrettyTable(['Symbol', 'Status', 'Buy Price', 'Current Price', 'P$', 'P%', 'Order Time'])
    R = "\033[0;31;40m" #RED
    G = "\033[0;32;40m" # GREEN
    N = "\033[0m" # Reset
    profit_list = []
    order_list = return_open_orders()
    last_run = datetime.datetime.fromtimestamp(last_run).strftime('%m-%d-%Y %H:%M:%S')
    for order in order_list:
        symbol = order['symbol']
        split_symbol = symbol.split('/')
        buy_price = order['buy_price']
        buy_amount = order['buy_amount']
        amount_spent = buy_price * buy_amount
        status = order['status']
        current_price = get_current_price(symbol)
        if status == 'open':
            ts = datetime.datetime.fromtimestamp(order['buy_time']).strftime('%m-%d-%Y %H:%M:%S')
        else:
            current_price = order['sell_price']
            ts = datetime.datetime.fromtimestamp(order['sell_time']).strftime('%m-%d-%Y %H:%M:%S')
            profit_list.append(order['sell_profit'])
        p_l_a = (current_price - buy_price)
        p_l_p = 100 * p_l_a / ((current_price + buy_price) / 2)
        p_l_d = (p_l_a / ((current_price + buy_price) / 2) * amount_spent) + amount_spent;
        p_l_d = p_l_d - amount_spent
        if p_l_a > 0:
            t.add_row([symbol, status, buy_price, current_price, "%s%s%s %s" % (G, round(p_l_d, 2), N, split_symbol[-1]), "%s%s%s %%" % (G, round(p_l_p, 2), N), ts])
        else:
            t.add_row([symbol, status, buy_price, current_price, "%s%s%s %s" % (R, round(p_l_d, 2), N, split_symbol[-1]), "%s%s%s %%" % (R, round(p_l_p, 2), N), ts])
    if os.name == 'nt': # Handle windows
        os.system('cls')
    else:
        os.system('clear')
    t.reversesort = True
    sum_profit = return_closed_profit()
    if sum_profit > 0:
        color = G
    elif sum_profit < 0:
        color = R
    else:
        color = N
    print("Last Check: %s - Coinbase Advanced Trading Bot  -  Total P$: %s%s%s" % (last_run, color, round(sum_profit,2), N))
    print(t.get_string(sortby="Order Time"))

    print("Websocket Up: %s" % (ws_status))

def get_current_price(symbol):
    global current_prices
    global ws_status
    if current_prices[symbol.replace('/', '-')] and current_prices[symbol.replace('/', '-')]['timestamp'] >= time.time() - 5: # Check for fresh websocket data before using it 
        current_price = current_prices[symbol.replace('/', '-')]['price']
    else:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        ws_status = False
    return current_price

def calculate_sma(df, period):
    return df['close'].rolling(window=period).mean()

def main():
    # To preload my order
    #insert_order('open', 'SHIB/USD', 77416742.61585483, 1698787595, 0.00000768)
    global since_start
    last_run = None
    while True:
        last_timetamp = time.time() # In case nothing comes through, we set this to now.
        try:
            if not last_run or time.time() >= last_run + sleep_lookup[timeframe]: # Determine if we need to refresh
                for symbol in symbols:
                    df = fetch_ohlcv_data(symbol)
                    if len(df) < 1:
                        print("%s doesn't appear to be a valid symbol on Coinbase A.T. Please remove it from your list of symbols above, and restart the bot." % symbol)
                        continue # This symbol doesn't exist on coinbase.
                    df = macd_signals(df,symbol)
                    df['fast_sma'] = calculate_sma(df, fast_sma_period)
                    df['slow_sma'] = calculate_sma(df, slow_sma_period)
                    macd = df['MACD_12_26_9'].iloc[-1]
                    macd_last = df['MACD_12_26_9'].iloc[len(df) - 2]
                    signal = df['MACDs_12_26_9'].iloc[-1]
                    signal_last = df['MACDs_12_26_9'].iloc[len(df) - 2]

                    close = df['close'].iloc[-1]
                    rsi = df['RSI_14'].iloc[-1]
                    fast_sma_current = df['fast_sma'].iloc[-1]
                    slow_sma_current = df['slow_sma'].iloc[-1]
                    fast_sma_previous = df['fast_sma'].iloc[len(df) - 2]
                    slow_sma_previous = df['slow_sma'].iloc[len(df) - 2]
                    last_timetamp = df['timestamp'].iloc[-1] / 1000

                    # Check for a buy signal
                    if risk_level == 'safe':
                        # Buy Low Risk
                        if fast_sma_previous < slow_sma_previous and fast_sma_current > slow_sma_current and macd > signal:
                            if not allow_duplicates and open_order_count(symbol) > 0: # Prevent duplicate coin
                                continue
                            if open_order_count() > max_orders: # Already met our max open orders
                                continue
                            if last_order_buy_price(symbol) > get_current_price(symbol): # Don't buy if we paid more for the last order
                                continue
                            # Check for an order that fired at on the same epoch and symbol
                            if not search_open_duplicate_timestamp(symbol, last_timetamp):
                                # DO BUY
                                current_price = get_current_price(symbol)
                                buy_amount = max_order_amount / current_price
                                buy_time = time.time()
                                insert_order('open', symbol, buy_amount, buy_time, last_timetamp, current_price)
                        # Sell Low Risk
                        elif fast_sma_previous > slow_sma_previous and fast_sma_current < slow_sma_current and macd < signal:
                            # DO SELL
                            if not search_open_order(symbol):
                                continue # No open orders for this coin
                            # DO SELL
                            current_price = get_current_price(symbol)
                            buy_orders = search_order(symbol)
                            for buy_order in buy_orders:
                                id = buy_order['doc_id']
                                buy_price = buy_order['buy_price']
                                buy_amount = buy_order['buy_amount']
                                p_l_a = (current_price - buy_price)
                                p_l_p = 100 * p_l_a / ((close + buy_price) / 2)
                                profit = (buy_amount * current_price) - (buy_price * buy_amount)
                                update_order(id, current_price, p_l_a, profit, time.time())
                    else:
                        # Buy Good Risk
                        if macd > signal and macd_last < signal_last and rsi < 50:
                            # Prevent duplicate coin
                            if not allow_duplicates and open_order_count(symbol) > 0: # Prevent duplicate coin
                                continue
                            if open_order_count() > max_orders: # Already met our max open orders
                                continue
                            if last_order_buy_price(symbol) > get_current_price(symbol): # Don't buy if we paid more for the last order
                                continue
                            # Check for an order that fired at on the same epoch and symbol
                            if not search_open_duplicate_timestamp(symbol, last_timetamp): 
                                # DO BUY
                                current_price = get_current_price(symbol)
                                buy_amount = max_order_amount / current_price
                                buy_time = time.time()
                                insert_order('open', symbol, buy_amount, buy_time, last_timetamp, current_price)
                        # Sell Good Risk
                        elif macd < signal and macd_last > signal_last  and rsi > 50:
                            # DO SELL
                            if not search_open_order(symbol):
                                continue
                            current_price = get_current_price(symbol)
                            buy_orders = search_order(symbol)
                            for buy_order in buy_orders:
                                id = buy_order['doc_id']
                                buy_price = buy_order['buy_price']
                                buy_amount = buy_order['buy_amount']
                                p_l_a = (current_price - buy_price)
                                profit = (buy_amount * current_price) - (buy_price * buy_amount)
                                update_order(id, current_price, p_l_a, profit, time.time())
                last_run = last_timetamp # last timestamp in the data we got
            print_orders(last_run)
            if ws_status:
                time.sleep(0.25)  # Sleep for timeframe
            else:
                time.sleep(1)
        except ccxt.RequestTimeout as e:
            # recoverable error, do nothing and retry later
            print(type(e).__name__, str(e))
        except ccxt.DDoSProtection as e:
            # recoverable error, you might want to sleep a bit here and retry later
            print(type(e).__name__, str(e))
        except ccxt.ExchangeNotAvailable as e:
            # recoverable error, do nothing and retry later
            print(type(e).__name__, str(e))
        except ccxt.NetworkError as e:
            # do nothing and retry later...
            print(type(e).__name__, str(e))
        except ccxt.ExchangeError as e:
            print(type(e).__name__, str(e))
            time.sleep(10)
        #except Exception as e:
        #    # panic and halt the execution in case of any other error
        #    print(type(e).__name__, str(e))
        #    sys.exit()


if __name__ == "__main__":
    main()

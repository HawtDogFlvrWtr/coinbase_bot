import argparse
import configparser
import datetime
import hashlib
import hmac
import requests
import json
import os
import sys
import ccxt
import math
import pandas as pd
import pandas_ta as ta
import time
from prettytable import PrettyTable
from tinydb import TinyDB, Query
from threading import Thread
import telebot
from websocket import create_connection, WebSocketConnectionClosedException # websocket-client

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--orders_file', help="The json filename for the orders file", default='cbb_database.json')
parser.add_argument('-c', '--config_file', help="The name of your config file", default='config.cfg')
parser.add_argument('-d', '--daemon', help="Running this bot in daemon mode shows no display on the console for privacy.", action='store_true')



# Argument setup
args = parser.parse_args()
orders_json_filename = args.orders_file
config_file = args.config_file
daemon = args.daemon
sleep_lookup = {'1m': 61, '1h': 3660, '1d': 84060} # Added second to give the exchange time to update the candles
start_time = datetime.datetime.fromtimestamp(time.time()).strftime('%m-%d-%Y %H:%M:%S')

# Notice
if not daemon:
    print('\033[0;31;40mI have made every attempt to ensure the accuracy and reliability of this application.\nHowever, this application is provided "as is" without warranty or support of any kind.\nI do not accept any responsibility or liability for the accuracy, content, completeness,\nlegality, or reliability of this application. Donations are welcome but doing so does not\nprovide you support for this project.\n\nBTC Wallet: 3CyQ5LW9Ycuuu8Ddr5de5goWRh95C4rN8E\nETH Wallet: 0x7eBEe95Af86Ed7f4B0eD29A322F1b811AD61DF36\nSHIB Wallet: 0x8cCc65a7786Bd5bf74E884712FF55C63b36B0112\n\nUse this application at your own risk.\033[0m')
    time.sleep(5)

# Config File Settings
config = configparser.ConfigParser()
config.read(config_file)

# Api Config
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')
telegram_key = config.get('api-config', 'telegram_key')
telegram_userid = config.get('api-config', 'telegram_userid')

# Spending Config
spend_dollars = int(config.get('spend-config', 'spend_dollars'))
buy_percent = int(config.get('spend-config', 'buy_percent'))
allow_duplicates = config.get('spend-config', 'allow_duplicates')
compound_spending = config.get('spend-config', 'compound_spending')

# Bot Config
timeframe = config.get('bot-config', 'timeframe')
symbols = json.loads(config.get('bot-config', 'symbols'))
stoploss_percent = float(json.loads(config.get('bot-config', 'stoploss_percent')))
if stoploss_percent > 0:
    print("Your stoploss_percent setting in your config is a positive number. Please set it to a negative number. Ex: -20")
    sys.exit()
take_profit = float(json.loads(config.get('bot-config', 'take_profit')))
rsi_buy_lt = int(json.loads(config.get('bot-config', 'rsi_buy_lt')))
buy_when_higher = config.get('bot-config', 'buy_when_higher')


# File checksum
current_checksum = hashlib.md5(open('coinbase_bot.py', 'rb').read()).hexdigest()
last_checksum = None

# Locals/Globals Setup
current_prices = {}
ws_status = 'Down'
exchange_issues = 0
ws_restarts = 0
bot_log = 'bot_logs.txt'

# Should we setup telegram?
try:
    bot = telebot.TeleBot(telegram_key)
except:
    bot = None

# Order Setup
max_order_amount = buy_percent / 100 * spend_dollars
max_orders = int(spend_dollars / max_order_amount)

# Database Setup
db = TinyDB(orders_json_filename, indent=4)
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

def get_online_checksum():
    try:
        online_checksum = requests.get('https://raw.githubusercontent.com/HawtDogFlvrWtr/coinbase_bot/main/coinbase_bot.py.checksum').text
        return online_checksum
    except:
        return False
    
def get_public_ip(): 
    try: 
        response = requests.get('https://httpbin.org/ip') 
        if response.status_code == 200: 
            ip_data = response.json() 
            public_ip = ip_data.get('origin') 
            return public_ip 
        else: 
            return False
    except Exception as e: 
        return False

def update_config(section, setting, value):
    global config_file
    config.read(config_file)
    config.set(section, setting, str(value))
    with open(config_file, 'w') as configfile:
        config.write(configfile)
        

# Daemons Start
def ws_daemon():
    global current_prices
    global api_key
    global secret
    global ws
    global symbols
    global ws_status
    global ws_restarts
    channel = "ticker"
    timestamp = str(int(time.time()))
    product_ids = []
    for symbol in symbols:
        product_ids.append(symbol.replace("/", '-'))
    product_ids_str = ",".join(product_ids)
    while True:
        ws_status = 'Up'
        try:
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
        except WebSocketConnectionClosedException as e:
            ws_restarts += 1
            ws_status = 'Down'
            pass

def telegram_bot():
    global bot
    global exchange_issues
    global ws_status
    global ws_restarts
    while True:
        try:
            @bot.message_handler(commands=['help'])
            def handle_help(message):
                bot.send_chat_action(message.chat.id, 'typing')
                # Provide a list of available commands and their descriptions
                help_text = '''/help     Show available commands.\n/orders Display your open orders.\n/status  Displays bot info.\n/rsi_buy_lt <int> Sets the rsi buy <\n/take_profit <int> Sets the take profit config\n/stoploss_percent <negative int> Sets the stoploss percent config\n/buy_percent <int> sets the buy percent in the config\n/spend_dollars <int> Sets the spend dollar ammount in the config'''
                bot.reply_to(message, help_text)

            @bot.message_handler(commands=['rsi_buy_lt'])
            def handle_rsi_buy_lt(message):
                bot.send_chat_action(message.chat.id, 'typing')
                tele_rsi_buy_lt = int(message.text.split(" ")[1])
                if not isinstance(tele_rsi_buy_lt, int):
                    bot.reply_to(message, "%s doesn't appear to be an integer" % tele_rsi_buy_lt)
                elif tele_rsi_buy_lt > 100 or tele_rsi_buy_lt < 0:
                    bot.reply_to(message, "%s doesn't appear to be an integer greater than 0 and less than 100" % tele_rsi_buy_lt)
                else:
                    bot.reply_to(message, "Setting Buy RSI to %s" % tele_rsi_buy_lt)
                    global rsi_buy_lt
                    rsi_buy_lt = tele_rsi_buy_lt
                    update_config('bot-config', 'rsi_buy_lt', tele_rsi_buy_lt)

            @bot.message_handler(commands=['take_profit'])
            def handle_take_profit(message):
                bot.send_chat_action(message.chat.id, 'typing')
                tele_take_profit = float(message.text.split(" ")[1])
                if not isinstance(tele_take_profit, float):
                    bot.reply_to(message, "%s doesn't appear to be an integer" % tele_take_profit)
                elif tele_take_profit > 100 or tele_take_profit <= 0:
                    bot.reply_to(message, "%s doesn't appear to be an integer greater than 0 and less than 100" % tele_take_profit)
                else:
                    bot.reply_to(message, "Setting Take Profit to %s" % tele_take_profit)
                    global take_profit
                    take_profit = tele_take_profit
                    update_config('bot-config', 'take_profit', tele_take_profit)

            @bot.message_handler(commands=['stoploss_percent'])
            def handle_stoploss_percent(message):
                bot.send_chat_action(message.chat.id, 'typing')
                tele_stoploss_percent = float(message.text.split(" ")[1])
                if not isinstance(tele_stoploss_percent, float):
                    bot.reply_to(message, "%s doesn't appear to be an integer" % tele_stoploss_percent)
                elif tele_stoploss_percent >= 0:
                    bot.reply_to(message, "%s doesn't appear to be an integer less than 0" % tele_stoploss_percent)
                else:
                    bot.reply_to(message, "Setting Stoploss to %s" % tele_stoploss_percent)
                    global stoploss_percent
                    stoploss_percent = float(tele_stoploss_percent)
                    update_config('bot-config', 'stoploss_percent', stoploss_percent)

            @bot.message_handler(commands=['spend_dollars'])
            def handle_spend_dollars(message):
                bot.send_chat_action(message.chat.id, 'typing')
                tele_spend_dollars = float(message.text.split(" ")[1])
                if not isinstance(tele_spend_dollars, float) or tele_spend_dollars == 0:
                    bot.reply_to(message, "%s doesn't appear to be an integer" % tele_spend_dollars)
                else:
                    bot.reply_to(message, "Setting SpendDollars to %s" % tele_spend_dollars)
                    global spend_dollars
                    spend_dollars = float(tele_spend_dollars)
                    update_config('spend-config', 'spend_dollars', spend_dollars)

            @bot.message_handler(commands=['buy_percent'])
            def handle_buy_percent(message):
                bot.send_chat_action(message.chat.id, 'typing')
                tele_buy_percent = float(message.text.split(" ")[1])
                if not isinstance(tele_buy_percent, float) or tele_buy_percent == 0:
                    bot.reply_to(message, "%s doesn't appear to be an integer" % tele_buy_percent)
                else:
                    bot.reply_to(message, "Setting SpendDollars to %s" % tele_buy_percent)
                    global buy_percent
                    buy_percent = float(tele_buy_percent)
                    update_config('spend-config', 'buy_percent', stoploss_percent)

            @bot.message_handler(commands=['status'])
            def handle_status(message):
                ip_address = get_public_ip()
                if not ip_address:
                    ip_address = 'unknown'
                bot.send_chat_action(message.chat.id, 'typing')
                status_pull = exchange.fetchStatus()
                status = status_pull['status']
                eta = status_pull['eta']
                url = status_pull['url']
                online_checksum = get_online_checksum()[0:5]
                string = '-General Info-\nBot start time: %s\nMy Version: %s\nLatest Version: %s\nPublic IP: %s\nWebsocket %s\nWebsocket reconnects: %s\nExchange reconnects: %s\n\n-Exchange Info-\nExchange Status: %s\nExchange Res. ETA: %s\nExchange Issue URL: %s\n\n-Spend Config-\nSpend Dollars: %s\nBuy Percent: %s\n\n-Bot Config-\nBuy RSI LT: %s\nTake Profit: %s\nStoploss: %s' % (start_time, current_checksum[0:5], online_checksum[0:5], ip_address, ws_status, ws_restarts, exchange_issues, status, eta, url, spend_dollars, buy_percent, rsi_buy_lt, take_profit, stoploss_percent)
                bot.reply_to(message, string)

            @bot.message_handler(commands=['orders'])
            def handle_orders(message):
                bot.send_chat_action(message.chat.id, 'typing')
                bot.reply_to(message, '<pre>%s</pre>' % print_orders(), parse_mode='html')
            bot.infinity_polling()
        except telebot.apihelper.ApiTelegramException as e:
            print("Telegram key is incorrect or config items missing.")
        except TimeoutError as e:
            time.sleep(5)
            pass
# Daemons End


def add_note(note):
    global telegram_userid
    global bot
    with open(bot_log, 'a+') as b_log: # Log to our log file
        b_log.write("%s\n" % note)
    if bot:
        try:
            bot.send_message(telegram_userid, note)
        except: # who cares if we can't send the text
            pass

def insert_order(status, symbol, amount, timestamp, signal_time, price, order_id, side, average, order_type, filled, remaining, cost, matching_order_id = None):
    db.insert(
        {
            'symbol': symbol,
            'status': status,
            'amount': amount,
            'timestamp': timestamp,
            'signal_time': signal_time,
            'price': price,
            'order_id': order_id,
            'matching_order_id': matching_order_id,
            'side': side,
            'type': order_type,
            'average': average,
            'filled': filled,
            'remaining': remaining,
            'cost': cost,
        }
    )

# Update the status of an order based on order id from Coinbase
def update_order(order_id, status):
    db.update({ 'status': status }, Orders.order_id == order_id)

# Search for opens given a status and a symbol
def search_open_order(symbol, status):
    results = db.search((Orders.symbol == symbol) & (Orders.status == status))
    if len(results) > 0:
        return True
    else:
        return False

# Get the last buy price by timestamp and symbol
def last_order_buy_price(symbol):
    od = sorted(db.search((Orders.symbol == symbol) & (Orders.status == 'buy_open')), key=lambda k: k['timestamp'])
    if not od:
        return False
    else:
        return od[-1]['price']
    
# Count open orders with or without symbol/side information
def open_order_count(symbol = None, side = None):
    if side == 'buy': # Buy
        status = 'buy_open'
    elif side == 'sell': # Sell
        status = 'open'
    else: # Both
        if not symbol:
            return db.count((Orders.status == 'open') | (Orders.status == 'buy_open'))
        else:
            return db.count((Orders.symbol == symbol) & ((Orders.status == 'open') | (Orders.status == 'buy_open')))
    
    # Handle single return above else
    if not symbol:
        return db.count((Orders.status == status))
    else:
        return db.count((Orders.symbol == symbol) & (Orders.status == status))
    
# Check to make sure we didn't already open a buy for a signal
def search_open_duplicate_timestamp(symbol, timestamp): # TODO: need to handle side and update calls
    results = db.search((Orders.symbol == symbol) & (Orders.signal_time == timestamp) & (Orders.status == 'buy_open'))
    if len(results) > 0:
        return True
    else:
        return False

# Get all records with or without symbol    
def search_order(symbol = None):
    if symbol:
        results = db.search(Orders.symbol == symbol)
        return results
    else:
        results = db.all()
        return results

# Return all open orders # TODO: Need to consolidate this with above search_order
def return_open_orders():
    results = db.search((Orders.status == 'buy_open') | (Orders.status == 'open'))
    return results

# Unused for now until we figure out how to better calculate profit # TODO: get profit display working again or remove
def return_closed_profit():
    results = db.search((Orders.side == 'sell') & (Orders.status == 'closed'))
    profit_list = []
    for res in results:
        profit_list.append(res['sell_profit'])
    return sum(profit_list)

# Signal Data Start

# Pull latest candles and throw into a dataframe
def fetch_ohlcv_data(symbol):
    global exchange_issues
    while True: # If we don't return, repeat until we do
        try:
            ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe)
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except ccxt.RequestTimeout as e:
            exchange_issues += 1
            pass
        except ccxt.DDoSProtection as e:
            exchange_issues += 1
            pass
        except ccxt.ExchangeNotAvailable as e:
            exchange_issues += 1
            pass
        except ccxt.NetworkError as e:
            exchange_issues += 1
            pass
        except ccxt.ExchangeError as e:
            exchange_issues += 1
            pass
       
# Generate macd information for the signals
def macd_signals(df):
    fast = 12
    slow = 26
    signal = 9
    macd = df.ta.macd(fast=fast, slow=slow, signal=signal)
    df = pd.concat([df, macd], axis=1)
    df = pd.concat([df, df.ta.rsi()], axis=1)
    return df

# Signal Data End

# Print orders function for telegram and console
def print_orders(last_run = None):
    global current_prices
    global ws_status
    if not last_run:
        t = PrettyTable(['Sym.', 'S.', 'Cur. Price', 'P%', 'Time'])
    else:
        t = PrettyTable(['Symbol', 'Side', 'Buy Price', 'Current Price', 'P$', 'P%', 'Time'])
    R = "\033[0;31;40m" #RED
    G = "\033[0;32;40m" # GREEN
    N = "\033[0m" # Reset
    order_list = return_open_orders()
    open_orders = open_order_count()
    for order in order_list:
        symbol = order['symbol']
        split_symbol = symbol.split('/')
        buy_price = order['price']
        buy_amount = order['amount']
        amount_spent = buy_price * buy_amount
        status = order['status']
        side = order['side']
        current_price = get_current_price(symbol)
        ts = datetime.datetime.fromtimestamp(order['timestamp']).strftime('%m-%d-%Y %H:%M')
        p_l_a = (current_price - buy_price)
        p_l_p = round((p_l_a / buy_price) * 100, 2)
        p_l_d = (p_l_a / ((current_price + buy_price) / 2) * amount_spent)
        if not last_run:
            t.add_row([symbol, side, current_price, "%s %%" % (round(p_l_p, 2)), ts])
        else:
            if p_l_a > 0:
                t.add_row([symbol, side, buy_price, current_price, "%s%s%s %s" % (G, round(p_l_d, 2), N, split_symbol[-1]), "%s%s%s %%" % (G, round(p_l_p, 2), N), ts])
            else:
                t.add_row([symbol, side, buy_price, current_price, "%s%s%s %s" % (R, round(p_l_d, 2), N, split_symbol[-1]), "%s%s%s %%" % (R, round(p_l_p, 2), N), ts])
    if os.name == 'nt': # Handle windows
        os.system('cls')
    else:
        os.system('clear')
    t.reversesort = True
    if last_run:
        last_run = datetime.datetime.fromtimestamp(last_run).strftime('%m-%d-%Y %H:%M')
        print("Last Check: %s - Open Orders: %s/%s" % (last_run, open_orders, max_orders))

    status = t.get_string(sortby="Time")
    return status

# Get current price from websocket info if it's not stale, and if so get all tickers and update them via the standard v2 api
def get_current_price(symbol):
    global current_prices
    global exchange_issues
    clean_symbol = symbol.replace('/', '-')
    while True: # Retry if we get no return.. Assume except
        if clean_symbol in current_prices and current_prices[clean_symbol]['timestamp'] >= time.time() - 10: # Check for fresh websocket data before using it 
            current_price = current_prices[clean_symbol]['price']
            return current_price
        else:
            try:
                tickers = exchange.fetch_tickers()
                for ticker in tickers:
                    timestamp = time.time()
                    current_prices[ticker] = {'price': float(tickers[ticker]['last']), 'timestamp': timestamp}
                current_price = current_prices[symbol]['price']
                return current_price
            except ccxt.RequestTimeout as e:
                exchange_issues += 1
            except ccxt.DDoSProtection as e:
                exchange_issues += 1
            except ccxt.ExchangeNotAvailable as e:
                exchange_issues += 1
            except ccxt.NetworkError as e:
                exchange_issues += 1
            except ccxt.ExchangeError as e:
                exchange_issues += 1
            except TypeError as e:
                exchange_issues += 1

# Update orders that aren't closed or have currency left for purchase
def check_unfilled_orders():
    global exchange_issues
    global compound_spending
    global spend_dollars
    orders = db.search((Orders.status == 'open') | (Orders.status == None) | (Orders.filled == None))
    for order in orders:
        order_id = order['order_id']
        symbol = order['symbol']
        side = order['side']
        price = float(order['price'])
        try:
            open_order = exchange.fetchOrder(order_id, symbol)
            filled = float(open_order['filled'])
            remaining = float(open_order['remaining'])
            fee = float(open_order['fee']['cost'])
            average = float(open_order['average'])
            status = open_order['status']
            if side == 'buy' and status != 'closed': # Make sure we don't change buy side until we close the sell.
                status = 'buy_open'
            # Handle compounding on sell
            if remaining == 0 and filled > 0 and fee > 0 and compound_spending == 'True' and side == 'sell':
                buy_orders = db.search(Orders.order_id == order['matching_order_id'])
                for buy_order in buy_orders:
                    buy_total = math.floor((float(buy_order['price']) * float(buy_order['filled'])) - float(buy_order['cost']))
                    sell_total = math.floor((float(price) * float(filled)) - float(fee))
                    spend_dollars = spend_dollars + (sell_total - buy_total)
                    update_config('spend-config', 'spend_dollars', spend_dollars)
            db.update({ 'status': status, 'filled': filled, 'remaining': remaining, 'cost': fee, 'average': average }, Orders.order_id == order_id)
        except ccxt.RequestTimeout as e:
            exchange_issues += 1
        except ccxt.DDoSProtection as e:
            exchange_issues += 1
        except ccxt.ExchangeNotAvailable as e:
            exchange_issues += 1
        except ccxt.NetworkError as e:
            exchange_issues += 1
        except ccxt.ExchangeError as e:
            exchange_issues += 1

# Attempt to buy an order
def attempt_buy(buy_time, note_timestamp, buy_amount, symbol, current_price):
    global exchange_issues
    formatted_amount = exchange.amount_to_precision(symbol, buy_amount)
    formatted_price = str("{:f}".format(current_price)) # Because sometimes coinbase hates small floats
    try:
        buy_return = exchange.createOrder(symbol, 'limit', 'buy', formatted_amount, formatted_price, { 'clientOrderId': "%s-%s-buy" % (buy_time, symbol) })
        insert_order('buy_open', symbol, buy_amount, time.time(), note_timestamp, current_price, buy_return['id'], 'buy', buy_return['average'], 'limit', buy_return['filled'], buy_return['remaining'], buy_return['fee'])
        return buy_return
    except ccxt.InsufficientFunds as e:
        exchange_issues += 1
        add_note('%s - FAILED Buying (Insufficient Funds) %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
        return False
    except ccxt.PermissionDenied as e:
        exchange_issues += 1
        add_note('%s - FAILED Buying (Permission Denied) %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
        return False
    except ccxt.RequestTimeout as e:
        exchange_issues += 1
        # recoverable error, do nothing and retry later
        add_note('%s - FAILED Buying (RequestTimeout) %s %s at %s. Error: %s' % (note_timestamp, buy_amount, symbol, current_price, e))
        return False
    except ccxt.DDoSProtection as e:
        exchange_issues += 1
        # recoverable error, you might want to sleep a bit here and retry later
        add_note('%s - FAILED Buying (DDoSProtection) %s %s at %s. Error: %s' % (note_timestamp, buy_amount, symbol, current_price, e))
        return False
    except ccxt.ExchangeNotAvailable as e:
        exchange_issues += 1
        # recoverable error, do nothing and retry later
        add_note('%s - FAILED Buying (ExchangeNotAvailable) %s %s at %s. Error: %s' % (note_timestamp, buy_amount, symbol, current_price, e))
        return False
    except ccxt.NetworkError as e:
        exchange_issues += 1
        # do nothing and retry later...
        add_note('%s - FAILED Buying (Network Error) %s %s at %s. Error: %s' % (note_timestamp, buy_amount, symbol, current_price, e))
        return False
    except ccxt.ExchangeError as e:
        exchange_issues += 1
        add_note('%s - FAILED Buying (ExchangeError) %s %s at %s. Error: %s' % (note_timestamp, buy_amount, symbol, current_price, e))
        return False
    
# Attempt sell # TODO: Figure out why SHIB won't sell right.
def attempt_sell(note_timestamp, buy_amount, symbol, current_price, profit, buy_id):
    global exchange_issues
    global compound_spending
    global spend_dollars
    formatted_amount = exchange.amount_to_precision(symbol, buy_amount)
    current_price = str("{:f}".format(current_price)) # Because sometimes coinbase hates small floats
    try:
        sell_return = exchange.createOrder(symbol, 'limit', 'sell', formatted_amount, current_price)
        # Handle compounding
        if sell_return['remaining'] == 0 and sell_return['filled'] > 0 and sell_return['fee'] > 0 and compound_spending == 'True':
            buy_orders = db.search(Orders.order_id == buy_id)
            for buy_order in buy_orders:
                buy_total = math.floor((float(buy_order['price']) * float(buy_order['filled'])) - float(buy_order['cost']))
                sell_total = math.floor((float(current_price) * float(sell_return['filled'])) - float(sell_return['fee']))
                spend_dollars = spend_dollars + (sell_total - buy_total)
                update_config('spend-config', 'spend_dollars', spend_dollars)
        insert_order(sell_return['status'], symbol, buy_amount, time.time(), note_timestamp, current_price, sell_return['id'], 'sell', sell_return['average'], 'limit', sell_return['filled'], sell_return['remaining'], sell_return['fee'], buy_id)
        update_order(buy_id, 'closed') # Mark old buy as closed
        return sell_return
    except ccxt.InsufficientFunds as e:
        exchange_issues += 1
        add_note('%s - FAILED Selling (Insufficient Denied) %s %s at %s. Profit: %s' % (note_timestamp, formatted_amount, symbol, current_price, profit))
        return False
    except ccxt.PermissionDenied as e:
        exchange_issues += 1
        add_note('%s - FAILED Selling (Permission Denied) %s %s at %s. Profit: %s' % (note_timestamp, formatted_amount, symbol, current_price, profit))
        return False
    except ccxt.RequestTimeout as e:
        exchange_issues += 1
        # recoverable error, do nothing and retry later
        add_note('%s - FAILED Selling (RequestTimeout) %s %s at %s. Error: %s' % (note_timestamp, formatted_amount, symbol, current_price, e))
        return False
    except ccxt.DDoSProtection as e:
        exchange_issues += 1
        # recoverable error, you might want to sleep a bit here and retry later
        add_note('%s - FAILED Selling (DDoSProtection) %s %s at %s. Error: %s' % (note_timestamp, formatted_amount, symbol, current_price, e))
        return False
    except ccxt.ExchangeNotAvailable as e:
        exchange_issues += 1
        # recoverable error, do nothing and retry later
        add_note('%s - FAILED Selling (ExchangeNotAvailable) %s %s at %s. Error: %s' % (note_timestamp, formatted_amount, symbol, current_price, e))
        return False
    except ccxt.NetworkError as e:
        exchange_issues += 1
        # do nothing and retry later...
        add_note('%s - FAILED Selling (Network Error) %s %s at %s. Error: %s' % (note_timestamp, formatted_amount, symbol, current_price, e))
        return False
    except ccxt.ExchangeError as e:
        exchange_issues += 1
        add_note('%s - FAILED Selling (Exchange Error) %s %s at %s. Error: %s' % (note_timestamp, formatted_amount, symbol, current_price, e))
        return False

# Start telegram bot thread if it didn't fail above
if bot:
    t_worker = Thread(target=telegram_bot, args=())
    t_worker.daemon = True
    t_worker.start()

# Start websocket thread
worker = Thread(target=ws_daemon, args=())
worker.daemon = True
worker.start()

def main():
    global buy_percent
    global spend_dollars
    global rsi_buy_lt
    global last_checksum
    global current_checksum
    last_run = None
    while True:
        last_timetamp = time.time() # In case nothing comes through, we set this to now.
        if not last_run or time.time() >= last_run + sleep_lookup[timeframe]: # Determine if we need to refresh
            for symbol in symbols:
                # FOR DEBUG
                #add_note("Checking %s at %s" % (symbol, time.time()))
                df = fetch_ohlcv_data(symbol)
                if len(df) < 1:
                    add_note("%s doesn't appear to be a valid symbol on Coinbase A.T. Please remove it from your list of symbols above, and restart the bot." % symbol)
                    continue # This symbol doesn't exist on coinbase.
                df = macd_signals(df)
                macd = df['MACD_12_26_9'].iloc[-1]
                macd_last = df['MACD_12_26_9'].iloc[len(df) - 2]
                signal = df['MACDs_12_26_9'].iloc[-1]
                signal_last = df['MACDs_12_26_9'].iloc[len(df) - 2]
                rsi = df['RSI_14'].iloc[-1]
                last_timetamp = df['timestamp'].iloc[-1] / 1000
                note_timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%m-%d-%Y %H:%M:%S')
                current_price = get_current_price(symbol)
                # Buy
                if macd > signal and macd_last < signal_last and rsi <= rsi_buy_lt:
                    if allow_duplicates == 'False' and open_order_count(symbol) > 0: # Prevent duplicate coin
                        add_note('%s - Skipping buy of symbol %s because we already have an open order' % (note_timestamp, symbol))
                        continue
                    if open_order_count() >= max_orders: # Already met our max open orders
                        add_note('%s - Skipping buy of symbol %s because we are at our max orders.' % (note_timestamp, symbol))
                        continue
                    if buy_when_higher == 'False' and last_order_buy_price(symbol) > get_current_price(symbol): # Don't buy if we paid more for the last order
                        add_note('%s - Skipping buy of symbol %s because a previous buy was at a lower price.' % (note_timestamp, symbol))
                        continue
                    # Check for an order that fired at on the same epoch and symbol
                    if not search_open_duplicate_timestamp(symbol, last_timetamp): 
                        # DO BUY
                        buy_amount = max_order_amount / current_price
                        buy_attempt = attempt_buy(time.time(), note_timestamp, buy_amount, symbol, current_price)
                        if buy_attempt != False:
                            add_note('%s - Buying %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
            last_run = last_timetamp # last timestamp in the data we got
            # Check for stoploss and take profit on the timeframe
            buy_orders = search_order()
            for buy_order in buy_orders:
                if buy_order['status'] != 'buy_open':
                    continue
                symbol = buy_order['symbol']
                current_price = get_current_price(symbol)
                order_id = buy_order['order_id']
                buy_price = buy_order['price']
                buy_amount = buy_order['amount']
                profit = round(((current_price - buy_price) / buy_price) * 100, 2)
                if int(profit) <= stoploss_percent: # Stoploss
                    sell_attempt = attempt_sell(note_timestamp, buy_amount, symbol, current_price, profit, order_id)
                    if sell_attempt != False:
                        add_note('%s - STOPLOSS Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                if int(profit) >= take_profit: # Take Profit
                    sell_attempt = attempt_sell(note_timestamp, buy_amount, symbol, current_price, profit, order_id)
                    if sell_attempt != False:
                        add_note('%s - TAKE PROFIT Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
            online_checksum = get_online_checksum() # Lets see if there is a new version
            if online_checksum and online_checksum != current_checksum and online_checksum != last_checksum:
                add_note("%s - There is a new version (%s) of this bot available." % (note_timestamp, online_checksum[0:5]))
                last_checksum = online_checksum
        check_unfilled_orders() # Update open orders
        if not daemon:
            print(print_orders(last_run))
        if ws_status == 'Up':
            time.sleep(0.25)
        else:
            time.sleep(1)

if __name__ == "__main__":
    main()

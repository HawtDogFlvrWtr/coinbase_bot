import argparse
import configparser
import datetime
import json
import os
import sys
import time
import ccxt

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config_file', help="The json filename for the orders file", default='config.cfg')
parser.add_argument('-s', '--start_time', help="The start time for backtesting", type=int, default=1262322000)
parser.add_argument('-e', '--end_time', help="The end time for backtesting", type=int, default=time.time())

args = parser.parse_args()
config_file = args.config_file
start_time = args.start_time
end_time = int(args.end_time)
config = configparser.ConfigParser()
config.read(config_file)
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')
symbols = json.loads(config.get('bot-config', 'symbols'))
timeframe = config.get('bot-config', 'timeframe')

if not os.path.exists("backtesting_data"):
    os.makedirs("backtesting_data")

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
for symbol in symbols:
    since_start = start_time
    ohlcv_data = []
    last_time = 0
    file_path = "backtesting_data/%s_%s.json" % (symbol.replace('/', '-'), timeframe)
    if os.path.isfile(file_path):
        open_json = open(file_path)
        ohlcv_data = json.load(open_json)
        since_start = ohlcv_data[-1][0] / 1000
        print(since_start)
    while True:
        print("Downloading %s %s" % (symbol, datetime.datetime.fromtimestamp(since_start).strftime('%m-%d-%Y %H:%M:%S')))
        since = datetime.datetime.fromtimestamp(since_start).strftime('%Y-%m-%dT%H:%M:%SZ')
        latest_candle = exchange.fetch_ohlcv(symbol, timeframe, exchange.parse8601(since))
        if len(latest_candle) == 0:
            since_start = since_start + (60 * 60 * 300)
            continue
        for candles in latest_candle:
            ohlcv_data.append(candles)
        since_start = int(latest_candle[-1][0] / 1000)
        if since_start == last_time:
            break
        else:
            last_time = since_start
    json_object = json.dumps(ohlcv_data, indent=4)
    with open(file_path, "w") as outfile:
        outfile.write(json_object)

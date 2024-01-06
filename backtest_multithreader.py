import argparse
import datetime
import json
import os
from queue import Queue
import sys
from threading import Thread
import subprocess
import time
import glob
import hashlib
import pandas as pd

# Clean Files
files = glob.glob('backtesting_json/*')
for f in files:
  os.remove(f)

# Get 2 weeks ago
dt_now = datetime.datetime.now()
current_time = datetime.datetime(dt_now.year, dt_now.month, dt_now.day, dt_now.hour, 0, 0)
start_time_1wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 604800)
start_time_2wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 1209600)
start_time_3wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 1814400)
start_time_4wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 2419200)
default = "%s,%s,%s,%s" % (start_time_1wk, start_time_2wk, start_time_3wk, start_time_4wk)
# Setup
q = Queue(maxsize=0)
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--start_times', help="The start times for backtesting in epoch, comma separated", default="%s,%s,%s,%s" % (start_time_1wk, start_time_2wk, start_time_3wk, start_time_4wk) )
parser.add_argument('-t', '--threads', help="The number of threads to use", type=int, default=10)

args = parser.parse_args()
start_times = args.start_times.split(",")

num_threads = args.threads
update = subprocess.Popen('python .\download_backtest_data.py')
update.wait()

# Start service
def do_stuff(q):
  while True:
    get_item = q.get()
    if get_item:
        split_item = get_item.split(':')
        new_name = get_item.replace(':', '-')
        b = split_item[0]
        tp = split_item[1]
        sl = split_item[2]
        epoch = split_item[3]
        process = subprocess.Popen('python .\coinbase_bot_backtester.py -rb %s -t %s -sl %s -s %s' % (b,tp,sl,epoch), shell=True)
        #process = subprocess.Popen('python .\coinbase_bot_backtester.py -rb %s -t %s -sl %s -s %s >> backtesting_logs/%s.log' % (b,tp,sl,epoch,new_name), shell=True)
        process.wait()
        q.task_done()
iter = 0
for b in range(30,105,5): # Buy rsi starting at 30 because we got nothing before that
  for tp in range(1,10,1): # Take Profit
    for sl in range(5,35,5): # Stoploss
      for epoch in start_times:
        q.put("%s:%s:%s:%s" % (b,tp,sl,epoch))
        iter += 1

print("%s total jobs queued" % iter)

for i in range(num_threads):
  worker = Thread(target=do_stuff, args=(q,))
  worker.daemon = True
  worker.start()

q.join()

# Combine json outputs
files = glob.glob('backtesting_json/*.json')
json_list = {}
averages = {}
for file in files:
  with open(file, 'r') as open_json:
    json_object = json.load(open_json)

    start_epoch = json_object['start_epoch']
    take_profit = json_object['take_profit']
    stop_loss = json_object['stop_loss']
    buy_rsi = json_object['buy_rsi']
    profit = json_object['profit']
    md5_string = "%s:%s:%s" % (take_profit, stop_loss, buy_rsi)
    hash_filename = hashlib.md5(md5_string.encode()).hexdigest() ### VERIFY THIS WORKED ###
    if hash_filename in json_list:
      json_list[md5_string].append(profit)
    else:
      json_list[md5_string] = [profit]
      
for item in json_list:
  average = sum(json_list[item]) / len(json_list[item])
  print(item, average)
  averages[item] = average

highest_average = max(averages.values())
res = list(filter(lambda x: averages[x] == highest_average, averages))
split_res = res[-1].split(':')
take_profit = split_res[0]
stop_loss = split_res[1]
buy_rsi = split_res[2]

output_json = {
    'take_profit': take_profit,
    'stoploss_percent': stop_loss,
    'rsi_buy_lt': buy_rsi,
}
print("Highest Average is settings take_profit: %s, stop_loss: %s, buy_rsi: %s with %s profit" % (take_profit, stop_loss, buy_rsi, round(highest_average,2)))
# Output settings file for the bot.
with open("optimal_settings.json", "w") as outfile:
    outfile.write(json.dumps(output_json, indent=4))
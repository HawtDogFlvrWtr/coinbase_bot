import argparse
import datetime
from queue import Queue
import sys
from threading import Thread
import subprocess
import time

# Get 2 weeks ago
dt_now = datetime.datetime.now()
current_time = datetime.datetime(dt_now.year, dt_now.month, dt_now.day, dt_now.hour, 0, 0)
start_time_1wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 604800)
start_time_2wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 1.21e+6)
start_time_3wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 1.814e+6)
start_time_4wk = round((current_time - datetime.datetime(1970,1,1)).total_seconds() - 2.419e+6)
default = "%s,%s,%s,%s" % (start_time_1wk, start_time_2wk, start_time_3wk, start_time_4wk)
# Setup
q = Queue(maxsize=0)
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--start_times', help="The start times for backtesting in epoch, comma separated", default="%s,%s,%s,%s" % (start_time_1wk, start_time_2wk, start_time_3wk, start_time_4wk) )
parser.add_argument('-t', '--threads', help="The number of threads to use", type=int, default=10)

args = parser.parse_args()
start_times = args.start_times.split(",")

num_threads = args.threads

# Start service
def do_stuff(q):
  while True:
    get_item = q.get()
    if get_item:
        split_item = get_item.split(':')
        new_name = get_item.replace(':', '-')
        print(new_name)
        b = split_item[0]
        tp = split_item[1]
        sl = split_item[2]
        epoch = split_item[3]
        process = subprocess.Popen('python .\coinbase_bot_backtester.py -rb %s -t %s -sl %s -s %s >> backtesting_logs/%s.log' % (b,tp,sl,epoch,new_name), shell=True)
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

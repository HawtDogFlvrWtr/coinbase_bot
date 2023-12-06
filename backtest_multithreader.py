import argparse
from queue import Queue
import sys
from threading import Thread
import subprocess

# Setup
q = Queue(maxsize=0)
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--start_times', help="The start times for backtesting in epoch, comma separated", default="1451606400,1672531200") # 2016,2023
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
        s = split_item[1]
        tp = split_item[2]
        sl = split_item[3]
        epoch = split_item[4]
        process = subprocess.Popen('python3 coinbase_bot_backtester.py -rb %s -rs %s -t %s -sl %s -s %s >> backtesting_logs/%s.log' % (b,s,tp,sl,epoch,new_name), shell=True)
        process.wait()
        q.task_done()

for b in range(30,105,5): # Buy rsi starting at 30 because we got nothing before that
  for s in range(0,85,5): # Sell rsi end at 81 because we got nothing after that
    for tp in range(5,35,5): # Take Profit
      for sl in range(5,35,5): # Stoploss
        for epoch in start_times:
          q.put("%s:%s:%s:%s:%s" % (b,s,tp,sl,epoch))

for i in range(num_threads):
  worker = Thread(target=do_stuff, args=(q,))
  worker.daemon = True
  worker.start()

q.join()
from progressivis import Scheduler, Every
from progressivis.stats import RandomTable, Min, Max
from progressivis.vis import Histograms

#log_level()

try:
    s = scheduler
    print('No scheduler defined, using the standard one')
except:
    s = Scheduler()

csv = RandomTable(columns=['a', 'b', 'c'],rows=1000000, throttle=1000, scheduler=s)
min = Min(scheduler=s)
min.input.table = csv.output.table
max = Max(scheduler=s)
max.input.table = csv.output.table
histograms = Histograms(scheduler=s)
histograms.input.table = csv.output.table
histograms.input.min = min.output.table
histograms.input.max = max.output.table
prlen = Every(scheduler=s)
prlen.input.df = histograms.output.table

if __name__=='__main__':
    print("Starting")
    csv.start()

from progressivis import *
from progressivis.vis import ScatterPlot
from progressivis.io import CSVLoader
from progressivis.datasets import get_dataset

import pandas as pd

def filter(df):
    lon = df['pickup_longitude']
    lat = df['pickup_latitude']
    return df[(lon>-74.08)&(lon<-73.5)&(lat>40.55)&(lat<41)]

def print_len(x):
    if x is not None:
        print len(x)

#log_level()

try:
    s = scheduler
except:
    s = Scheduler()

URLS = [
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-01.csv',
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-02.csv',
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-03.csv',
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-04.csv',
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-05.csv',
    'https://storage.googleapis.com/tlc-trip-data/2015/yellow_tripdata_2015-06.csv',
]

filenames = pd.DataFrame({'filename': URLS})
cst = Constant(df=filenames, scheduler=s)
csv = CSVLoader(index_col=False,skipinitialspace=True,usecols=['pickup_longitude', 'pickup_latitude'], filter=filter, scheduler=s)
csv.input.filenames = cst.output.df
pr = Every(scheduler=s)
pr.input.df = csv.output.df
scatterplot = ScatterPlot('pickup_longitude', 'pickup_latitude', scheduler=s)
scatterplot.create_dependent_modules(csv,'df')

if __name__=='__main__':
    csv.start()
    s.thread.join()
    print len(csv.df())

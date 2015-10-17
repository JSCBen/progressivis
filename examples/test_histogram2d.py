from progressivis import Scheduler, Every, Print
from progressivis.io import CSVLoader
from progressivis.stats import Histogram2D
from progressivis.datasets import get_dataset

print "Loading test_histogram2d"
print "Type of default_scheduler is %s" % type(Scheduler.default)

csv = CSVLoader(get_dataset('bigfile'),index_col=False,header=None,engine='c')
pr = Every()
pr.input.inp = csv.output.df
histogram2d=Histogram2D(1, 2, xbins=128, ybins=128)
histogram2d.input.df = csv.output.df
pr = Print(id='print')
pr.input.inp = histogram2d.output.histogram2d

if __name__=='__main__':
    csv.start()

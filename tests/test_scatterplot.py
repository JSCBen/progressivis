import unittest

from progressivis import *
from progressivis.stats import Stats
from progressivis.io import CSVLoader
from progressivis.vis import ScatterPlot
from progressivis.datasets import get_dataset

import pandas as pd
from pprint import pprint
import logging

def print_len(x):
    if x is not None:
        print len(x)

class TestScatterPlot(unittest.TestCase):
#    def setUp(self):
#        log_level(logging.INFO,'progressivis')

    def test_scatterplot(self):
        csv    = CSVLoader(get_dataset('bigfile'),index_col=False,header=None)
        sp = ScatterPlot(x_column=1, y_column=2)
        wait = sp.create_scatterplot_modules()
        wait.input.inp = csv.output.df
        cnt = Every(proc=print_len,constant_time=True)
        cnt.input.inp = csv.output.df
        prt = Print()
        prt.input.inp = sp.merge.output.df
        csv.scheduler().start()


if __name__ == '__main__':
    unittest.main()

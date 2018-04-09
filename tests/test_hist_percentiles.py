"Test for Range Query"
#import numpy as np
from progressivis.table.constant import Constant
from progressivis.table.table import Table
from progressivis import Print
from progressivis.stats import  RandomTable, Min, Max
from progressivis.core.bitmap import bitmap
from progressivis.table.hist_index import HistogramIndex
from progressivis.table.percentiles import Percentiles
import numpy as np
from . import ProgressiveTest, main, skip


class TestPercentiles(ProgressiveTest):
    "Tests for HistIndex based percentiles"
    def _impl_tst_percentiles(self, accuracy):
        """
        """
        s = self.scheduler()
        random = RandomTable(2, rows=10000, scheduler=s)
        hist_index = HistogramIndex(column='_1', scheduler=s)
        hist_index.input.table = random.output.table
        t_percentiles = Table(name=None,
                        dshape='{_25: float64, _50: float64, _75: float64}',
                        data={'_25': [25.0], '_50': [50.0], '_75': [75.0]})
        which_percentiles = Constant(table=t_percentiles, scheduler=s)
        #import pdb;pdb.set_trace()
        percentiles = Percentiles(hist_index, accuracy=accuracy, scheduler=s)
        percentiles.input.table = random.output.table
        percentiles.input.percentiles = which_percentiles.output.table
        prt = Print(proc=self.terse, scheduler=s)
        prt.input.df = percentiles.output.table
        s.start()
        s.join()
        pdict = percentiles.table().last().to_dict()
        v = random.table()['_1'].values
        p25 = np.percentile(v, 25.0)
        print(p25, pdict['_25'])
        self.assertAlmostEqual(p25, pdict['_25'], delta=0.01)
        p50 = np.percentile(v, 50.0)
        print(p50, pdict['_50'])
        self.assertAlmostEqual(p50, pdict['_50'], delta=0.01)
        p75 = np.percentile(v, 75.0)
        print(p75, pdict['_75'])
        self.assertAlmostEqual(p75, pdict['_75'], delta=0.01)
    def test_percentiles_fast(self):
        """test_percentiles: Simple test for HistIndex based percentiles
        low accurracy => faster mode
        """
        return self._impl_tst_percentiles(2.0)
    def test_percentiles_accurate(self):
        """test_percentiles: Simple test for HistIndex based percentiles
        higher accurracy => slower mode
        """
        return self._impl_tst_percentiles(0.2)
if __name__ == '__main__':
    main()

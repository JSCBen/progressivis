# -*- coding: utf-8 -*-
from progressive.core.dataframe import DataFrameModule

import pandas as pd
import numpy as np

from sklearn.feature_extraction import DictVectorizer
import re
import numpy as np

from bz2 import BZ2File
from gzip import GzipFile

def vec_loader(filename, dtype=np.float64):
    """Loads a tf-idf file in .vec format (or .vec.bz2).

Loads a file and returns a scipy sparse matrix of document features.
>>> mat,features=vec_loader('../data/warlogs.vec.bz2')
>>> mat.shape
(3077, 4337)
    """
    pattern = re.compile(r"\(([0-9]+),([-+.0-9]+)\)[ ]*")
    openf=open
    if filename.endswith('.bz2'):
        openf=BZ2File
    elif filename.endswith('.gz') or filename.endswith('.Z'):
        openf=GzipFile
    with openf(filename) as f:
        dataset = []
        for d in f:
            doc = {}
            for match in re.finditer(pattern, d):
                termidx = int(match.group(1))
                termfrx = dtype(match.group(2))
                doc[termidx] = termfrx
            if len(doc)!=0:
               dataset.append(doc) 

        dict = DictVectorizer(dtype=dtype,sparse=True)
        return (dict.fit_transform(dataset), dict.get_feature_names())


class VECLoader(DataFrameModule):
    pattern = re.compile(r"\(([0-9]+),([-+.0-9]+)\)[ ]*")
    parameters = [('chunksize', np.dtype(int), 1000)]
    
    def __init__(self, filename, dtype=np.float64, **kwds):
        super(VECLoader, self).__init__(**kwds)
        self._dtype = dtype
        self.default_step_size = kwds.get('chunksize', 1000)  # initial guess
        openf=open
        if filename.endswith('.bz2'):
            openf=BZ2File
        elif filename.endswith('.gz') or filename.endswith('.Z'):
            openf=GzipFile
        self.f = openf(filename)
        # When created with a specified chunksize, it returns the parser
        self._rows_read = 0

    def rows_read():
        return self._rows_read

    def run_step(self,run_number,step_size, howlong):
        if self.f is None:
            raise StopIteration()
        
        dataset = []
        try:
            while len(dataset) < step_size:
                line = self.f.next()
                line=line.rstrip('\n\r')
                if len(line)==0:
                    continue
                doc = {}
                for match in re.finditer(self.pattern, line):
                    termidx = int(match.group(1))
                    termfrx = self._dtype(match.group(2))
                    doc[termidx] = termfrx
                if len(doc)!=0:
                    dataset.append(pd.Series(doc) )
        except StopIteration:
            self.f.close()
            self.f = None

        creates = len(dataset)
        if creates==0:
            raise StopIteration()


        df = pd.DataFrame({'document': dataset, self.UPDATE_COLUMN: np.nan})
        self._rows_read += creates
        if self._df is not None:
            self._df = self._df.append(df,ignore_index=True)
        else:
            self._df = df
        return self._return_run_step(self.state_ready, steps_run=creates, creates=creates)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

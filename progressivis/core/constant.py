from . import DataFrameModule, ProgressiveError

import pandas as pd

class Constant(DataFrameModule):
    def __init__(self, df, **kwds):        
        super(Constant, self).__init__(**kwds)
        assert isinstance(df, pd.DataFrame)
        self._df = df
        self._df[self.UPDATE_COLUMN] = 1

    def predict_step_size(self, duration):
        return 1
    
    def run_step(self,run_number,step_size,howlong):
        raise StopIteration()

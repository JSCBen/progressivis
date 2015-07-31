from progressive.core.common import ProgressiveError
from progressive.core.utils import typed_dataframe
from progressive.core.dataframe import DataFrameModule
from progressive.core.slot import SlotDescriptor

import numpy as np
import pandas as pd

class Stats(DataFrameModule):
    def __init__(self, column, min_column=None, max_column=None, **kwds):
        self._add_slots(kwds,'input_descriptors',
                        [SlotDescriptor('df', type=pd.DataFrame, required=True)])
        super(Stats, self).__init__(dataframe_slot='stats', **kwds)
        self._column = column
        self.default_step_size = 10000

        if min_column is None:
            min_column = str(column) + '.min'
        if max_column is None:
            max_column = str(column) + '.max'
        self.min_column = min_column
        self.max_column = max_column
        self.schema = [(self.min_column, np.dtype(float), np.nan),
                       (self.max_column, np.dtype(float), np.nan),
                       DataFrameModule.UPDATE_COLUMN_DESC]
        self._df = typed_dataframe(self.schema)

    def is_ready(self):
        if not self.get_input_slot('df').is_buffer_empty():
            return True
        return super(Stats, self).is_ready()

    def run_step(self,run_number,step_size,howlong):
        dfslot = self.get_input_slot('df')
        input_df = dfslot.data()
        dfslot.update(run_number, input_df)
        if len(dfslot.deleted) or len(dfslot.updated) > len(dfslot.created):
            import pdb
            pdb.set_trace()
            raise ProgressiveError('%s module does not manage updates or deletes', self.__class__.__name__)
        dfslot.buffer_created()

        indices = dfslot.next_buffered(step_size)
        steps = len(indices)
        if steps == 0:
            return self._return_run_step(self.state_blocked, steps_run=steps)
        x = input_df.loc[indices, self._column]
        df = self._df
        df.loc[0] = [np.nanmin([df.at[0, self.min_column], x.min()]),
                     np.nanmax([df.at[0, self.max_column], x.max()]),
                     run_number]
        return self._return_run_step(self.state_ready, steps_run=steps, reads=steps, updates=len(self._df))

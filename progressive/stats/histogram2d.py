from progressive.core.common import ProgressiveError
from progressive.core.utils import typed_dataframe
from progressive.core.dataframe import DataFrameModule
from progressive.core.slot import SlotDescriptor

import numpy as np
import pandas as pd

class Histogram2d(DataFrameModule):
    parameter = [('xbins', dtype(int), 1024),
                 ('ybins', dtype(int), 1024),
                 ('xmin', dtype(float), 0),
                 ('xmax', dtype(float), 1),
                 ('ymin', dtype(float), 0),
                 ('ymax', dtype(float), 1),
                 ('xdelta', dtype(float), 0),
                 ('ydelta', dtype(float), 0)]
                 
    def __init__(self, **kwds):
        self._add_slots(kwds,'input_descriptors',
                        [SlotDescriptor('df', type=pd.DataFrame)])
        super(Histogram2d, self).__init__(dataframe_slot='histogram', **kwds)
        self.x_column = x_column
        self.y_column = y_column
        self.bins = bins
        self.default_step_size = 10000

        columns = ['sum', 'histogram'] + [self.UPDATE_COLUMN]
        dtypes = [np.dtype(float) np.dtype(object)]
        values = [0, None, np.nan]

        self._df = typed_dataframe(columns, dtypes, values)

    def is_ready(self):
        if not self.get_input_slot('df').is_buffer_empty():
            return True
        return super(Stats, self).is_ready()

    def run_step(self, step_size, howlong):
        dfslot = self.get_input_slot('df')
        input_df = dfslot.data()
        dfslot.update(self._start_time, input_df)
        if len(dfslot.deleted) or len(dfslot.updated) > len(dfslot.created):
            raise ProgressiveError('%s module does not manage updates or deletes', self.__class__.name)
        dfslot.buffer_created()

        indices = dfslot.next_buffered(step_size)
        steps = len(indices)
        if steps == 0:
            return self._return_run_step(self.state_blocked, steps_run=steps)
        x = input_df.loc[indices, self.x_column]
        y = input_df.loc[indices, self.y_column]
        histo, xedges, yedges = np.histogram2d(y, x, bins=self.bins)
        sum = histo.sum()
        df = self._df
        df.loc[0, 'count'] += x.count()
        df.loc[0, 'min']   = np.nanmin([df.loc[0, 'min'], x.min()])
        df.loc[0, 'max']   = np.nanmax([df.loc[0, 'max'], x.max()])
        df.loc[0, self.UPDATE_COLUMN] = np.nan  # to update time stamps
        return self._return_run_step(self.state_ready, steps_run=steps, reads=steps, updates=len(self._df))

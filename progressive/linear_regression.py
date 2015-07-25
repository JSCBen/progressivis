from progressive.common import ProgressiveError
from progressive.dataframe import DataFrameModule
from progressive.slot import SlotDescriptor

import numpy as np
import pandas as pd

class LinearRegression(DataFrameModule):
    def __init__(self, x_column, y_column, **kwds):
        self._x = x_column
        self._y = y_column
        self._add_slots(kwds,'input_descriptors',
                        [SlotDescriptor('in', type=pd.DataFrame)])
        super(LinearRegression, self).__init__(dataframe_slot='in', **kwds)
        self.default_step_size = 10000

        index = ['coef', 'intercept', 'sum_x', 'sum_x_sqr', 'sum_y', 'sum_xy']
        self._df = pd.DataFrame({'description': [np.nan, np.nan, 0, 0, 0, 0, 0],
                                 self.UPDATE_COLUMN: [self.EMPTY_TIMESTAMP]},
                                 index=index)

    def is_ready(self):
        if not self.get_input_slot('df').is_buffer_empty():
            return True
        return super(LinearRegression, self).is_ready()

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
        x = input_df.loc[indices, self._x]
        y = input_df.loc[indices, self._y]
        desc = self._df['description']
        sum_x     = desc['sum_x']     + x.sum() 
        sum_x_sqr = desc['sum_x_sqr'] + (x*x).sum()
        sum_y     = desc['sum_y']     + y.sum()
        sum_xy    = desc['sum_xy']    + (x*y).sum()
        denom = len(x) * sum_x_sqr - sum_x*sum_x
        coef = (sum_y*sum_x_sqr - sum_x*sum_xy) / denom
        intercept = (len(x)*sum_xy - sum_x*sum_y) / denom
        desc['sum_x'] = sum_x
        desc['sum_x_sqr'] = sum_x_sqr
        desc['sum_y'] = sum_y
        desc['sum_xy'] = sum_xy
        desc['coef'] = coef
        desc['intercept'] = intercept
        self._df[self.UPDATE_COLUMN] = np.nan # to update time stamps
        return self._return_run_step(self.state_ready, steps_run=steps, reads=steps, updates=len(desc))
        

from progressivis.core.utils import ProgressiveError, indices_len
from progressivis.core.dataframe import DataFrameModule
from .slot import SlotDescriptor
from .utils import is_valid_identifier
from .buffered_dataframe import BufferedDataFrame

import pandas as pd

import logging
logger = logging.getLogger(__name__)

class Select(DataFrameModule):
    def __init__(self, query_column='query', **kwds):
        self._add_slots(kwds,'input_descriptors',
                        [SlotDescriptor('df', type=pd.DataFrame, required=True),
                         SlotDescriptor('query', type=pd.DataFrame, required=False)])
        super(Select, self).__init__(**kwds)
        self.default_step_size = 1000
        self._query_column = query_column
        self._buffer = BufferedDataFrame()
        
    def create_dependent_modules(self, input_module, input_slot, **kwds):
        from progressivis import RangeQuery
        
        if hasattr(self, 'input_module'): # test if already called
            return self
        s=self.scheduler()
        self.input_module = input_module
        self.input_slot = input_slot

        query = RangeQuery(group=self.id,scheduler=s)
        query.create_dependent_modules(input_module, input_slot, **kwds)

        select = self
        select.input.df = input_module.output[input_slot]
        select.input.query = query.output.query

        self.query = query
        self.min = query.min
        self.max = query.max
        self.min_value = query.min_value
        self.max_value = query.max_value
        
        return select
        

    def run_step(self,run_number,step_size,howlong):
        query_slot = self.get_input_slot('query')
        df_slot = self.get_input_slot('df')
        if not query_slot:
            query = None
        else:
            query_df = query_slot.data()
            query_slot.update(run_number)
            if  query_slot.has_created(): # ignore deleted and updated
                df_slot.reset() # re-filter
                self._buffer.reset();
            indices = query_slot.next_created() # read it all
            with query_slot.lock:
                query = self.last_row(query_df)[self._query_column] # get the query expression
            if query is not None:
                if len(query)==0:
                    query=None
                else:
                    query = unicode(query) # make sure we have a string

        df_slot.update(run_number)
        if df_slot.has_deleted() or df_slot.has_updated():
            df_slot.reset()
            self._buffer.reset()
            df_slot.update(run_number)
        
        indices = df_slot.next_created(step_size)
        steps = indices_len(indices)
        if steps==0:
            return self._return_run_step(self.state_blocked, steps_run=steps)

        if query is None: # nothing to query, just pass through
            logger.info('No query, passing data through')
            self._df = df_slot.data()
            return self._return_run_step(self.state_blocked, steps_run=steps)
        
        if isinstance(indices, slice):
            indices = slice(indices.start, indices.stop-1)
        with df_slot.lock:
            new_df = df_slot.data().loc[indices]
            try:
                selected_df = new_df.eval(query)
                #print 'Select evaluated %d/%d rows'%(len(selected_df),steps)
                if isinstance(selected_df, pd.Series):
                    if selected_df.index.has_duplicates:
                        import pdb
                        pdb.set_trace()
                    selected_df = new_df.loc[selected_df]
            except Exception as e:
                logger.error('Probably a syntax error in query expression: %s', e)
                self._df = df_slot.data()
                return self._return_run_step(self.state_blocked, steps_run=steps)
            selected_df.loc[:,self.UPDATE_COLUMN] = run_number
            self._buffer.append(selected_df) #, ignore_index=False) TODO later
            self._df = self._buffer.df()
        return self._return_run_step(self.state_blocked, steps_run=steps)

    @staticmethod
    def make_range_query(column, low, high=None):
        if not is_valid_identifier(column):
            raise ProgressiveError('Cannot use column "%s", invalid name in expression',column)
        if high==None or low==high:
            return "({} == {})".format(low,column)
        elif low > high:
            low,high = high, low
        return "({} <= {} <= {})".format(low,column,high)

    @staticmethod
    def make_and_query(*expr):
        if len(expr)==1:
            return expr[0]
        elif len(expr)>1:
            return " and ".join(expr)
        return ""

    @staticmethod
    def make_or_query(*expr):
        if len(expr)==1:
            return expr[0]
        elif len(expr)>1:
            return " or ".join(expr)
        return ""

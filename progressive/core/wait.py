from progressive.core.common import ProgressiveError
from progressive import Module, SlotDescriptor

import numpy as np

class Wait(Module):
    parameters = [('delay', np.dtype(float), np.nan),
                  ('reads', np.dtype(int), 0)]

    def __init__(self, **kwds):
        self._add_slots(kwds,'output_descriptors', [SlotDescriptor('out')])
        self._add_slots(kwds,'input_descriptors', [SlotDescriptor('in')])
        super(Wait, self).__init__(**kwds)
        
    def is_ready(self):
        delay = self.params.delay
        reads = self.params.reads
        if delay==np.nan and reads==0:
            return False
        if delay!=np.nan and reads != 0:
            raise ProgressiveError('Module %s needs either a delay or a number of reads, not both', self.__class__.name)
        inslot = self.get_input_slot('in')
        if inslot.output_module is None:
            return False
        trace = inslot.output_module.tracer.df() 
        if delay != np.nan:
            return trace[Module.UPDATE_COLUMN].irow(-1) >= delay
        elif reads:
            return trace['reads'].irow(-1) >= reads
        return False

    def predict_step_size(self, duration):
        return 1
    
    def run_step(self, step_size, howlong):
        print 'running wait'
        raise StopIteration()

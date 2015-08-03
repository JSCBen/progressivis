from uuid import uuid4
from inspect import getargspec
from traceback import print_exc

import pandas as pd
import numpy as np
import random

import logging
logger = logging.getLogger(__name__)

from progressive.core.common import ProgressiveError
from progressive.core.utils import empty_typed_dataframe, typed_dataframe, DataFrameAsDict
from progressive.core.scheduler import *
from progressive.core.slot import *
from progressive.core.tracer import Tracer
from progressive.core.time_predictor import TimePredictor
from progressive.core.storagemanager import StorageManager

def connect(output_module, output_name, input_module, input_name):
    return output_module.connect_output(output_name, input_module, input_name)

class ModuleMeta(type):
    """Module metaclass is needed to collect the input parameter list in all_parameters.
    """
    def __init__(cls, name, bases, attrs):
        if not "parameters" in attrs:
            cls.parameters = []
        all_props = list(cls.parameters)
        for base in bases:
            all_props += getattr(base, "all_parameters", [])
        cls.all_parameters = all_props
        super(ModuleMeta, cls).__init__(name, bases, attrs)

class Module(object):
    __metaclass__ = ModuleMeta
    
    parameters = [('quantum', np.dtype(float), 1.0)]
        
    EMPTY_COLUMN = pd.Series([],index=[],name='empty')
    EMPTY_TIMESTAMP = 0
    UPDATE_COLUMN = '_update'
    UPDATE_COLUMN_TYPE = np.dtype(int)
    UPDATE_COLUMN_DESC = (UPDATE_COLUMN, UPDATE_COLUMN_TYPE, EMPTY_TIMESTAMP)
    TRACE_SLOT = '_trace'
    PARAMETERS_SLOT = '_params'

    state_created = 0
    state_ready = 1
    state_running = 2
    state_blocked = 3
    state_terminated = 4
    state_name = ['created', 'ready', 'running', 'blocked', 'terminated']

    def __init__(self,
                 id=None,
                 scheduler=None,
                 tracer=None,
                 predictor=None,
                 storage=None,
                 input_descriptors=[],
                 output_descriptors=[],
                 **kwds):
        if id is None:
            id = uuid4()
        if scheduler is None:
            scheduler = Scheduler.default
        if tracer is None:
            tracer = Tracer.default
        if predictor is None:
            predictor = TimePredictor.default
        if storage is None:
            storage = StorageManager.default

        # always present
        output_descriptors = output_descriptors + [SlotDescriptor(Module.TRACE_SLOT, type=pd.DataFrame, required=False)]
        
        input_descriptors = input_descriptors + [SlotDescriptor(Module.PARAMETERS_SLOT, type=pd.DataFrame, required=False)]
        self._id = id
        self._parse_parameters(kwds)
        self._scheduler = scheduler
        if self._scheduler.exists(id):
            raise ProgressiveError('module already exists in scheduler, delete it first')
        self.tracer = tracer
        self.predictor = predictor
        self.storage = storage
        self._start_time = None
        self._end_time = None
        self._last_update = None
        self._state = Module.state_created
        self._had_error = False
        self.input_descriptors = input_descriptors
        self.output_descriptors = output_descriptors
        self._input_slots = self._validate_descriptors(self.input_descriptors)
        self._input_types = {d.name: d.type for d in self.input_descriptors}
        self._output_slots = self._validate_descriptors(self.output_descriptors)
        self._output_types = {d.name: d.type for d in self.output_descriptors}
        self.default_step_size = 1
        self.input = InputSlots(self)
        self.output = OutputSlots(self)
        self._scheduler.add(self)

    @staticmethod
    def _filter_kwds(kwds, function_or_method):
        argspec = getargspec(function_or_method)
        keys = argspec.args[len(argspec.args)-len(argspec.defaults):]
        filtered_kwds = {k: kwds[k] for k in kwds.viewkeys()&keys}
        return filtered_kwds

    @staticmethod
    def _add_slots(kwds, kwd, slots):
        if kwd in kwds:
            kwds[kwd] += slots
        else:
            kwds[kwd] = slots

    @staticmethod
    def _validate_descriptors(descriptor_list):
        slots = {}
        for desc in descriptor_list:
            if desc.name in slots:
                raise ProgressiveError('Duplicate slot name %s in slot descriptor', desc.name)
            slots[desc.name] = None
        return slots

    @staticmethod
    def create_dataframe(columns, types=None, values=None):
        if values is None and types is not None:
            return empty_typed_dataframe(columns, types)
        return typed_dataframe(columns, types, values)

    @property
    def paramameters(self):
        return self._params

    def _parse_parameters(self, kwds):
        self._params = self.create_dataframe(self.all_parameters + [self.UPDATE_COLUMN_DESC])
        self.params = DataFrameAsDict(self._params)
        for (name,dtype,dflt) in self.all_parameters:
            if name in kwds:
                self.params[name] = kwds[name]

    def timer(self):
        return self._scheduler.timer()

    def describe(self):
        print 'type: %s' % type(self)
        print 'id: %s' % self.id()
        print 'quantum: %f' % self.params.quantum
        print 'start_time: %s' % self._start_time
        print 'end_time: %s' % self._end_time
        print 'last_update: %s' % self._last_update
        print 'state: %s(%d)' % (self.state_name[self._state], self._state)
        print 'input_slots: %s' % self._input_slots
        print 'outpus_slots: %s' % self._output_slots
        print 'default_step_size: %d' % self.default_step_size
        if len(self._params):
            print 'parameters: '
            print self._params

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return u'Module %s: %s' % (self.__class__.__name__, self.id())

    def __repr__(self):
        return self.__unicode__()

    def __hash__(self):
        return self._id.__hash__()

    def id(self):
        return self._id

    def scheduler(self):
        return self._scheduler

    def create_slot(self, output_name, input_module, input_name):
        return Slot(self, output_name, input_module, input_name)

    def connect_output(self, output_name, input_module, input_name):
        slot=self.create_slot(output_name, input_module, input_name)
        slot.connect()
        return slot

    def get_input_slot(self,name):
         # raises error is the slot is not declared
        return self._input_slots[name]

    def get_input_module(self,name):
        return self.get_input_slot(name).output_module

    def input_slot_values(self):
        return self._input_slots.values()

    def input_slot_type(self,name):
        return self._input_types[name]

    def input_slot_names(self):
        return self._input_slots.keys()

    def _connect_input(self, slot):
        ret = self.get_input_slot(slot.input_name)
        self._input_slots[slot.input_name] = slot
        return ret

    def _disconnect_input(self, slot):
        pass

    def validate_inputs(self):
        # Only validate existence, the output code will test types
        for sd in self.input_descriptors:
            slot = self._input_slots[sd.name]
            if sd.required and slot is None:
                raise ProgressiveError('Missing inputs slot %s in %s',
                                       sd.name, self._id)

    def get_output_slot(self,name):
         # raise error is the slot is not declared
        return self._output_slots[name]

    def output_slot_type(self,name):
        return self._output_types[name]

    def output_slot_values(self):
        return self._output_slots.values()

    def output_slot_names(self):
        return self._output_slots.keys()

    def validate_outputs(self):
        for sd in self.output_descriptors:
            slots = self._output_slots[sd.name]
            if sd.required and len(slots)==0:
                raise ProgressiveError('Missing output slot %s in %s',
                                       sd.name, self._id)
            if slots:
                for slot in slots:
                    slot.validate_types()

    def _connect_output(self, slot):
        slot_list = self.get_output_slot(slot.output_name)
        if slot_list is None:
            self._output_slots[slot.output_name] = [ slot ]
        else:
            slot_list.append(slot)
        return slot_list

    def _disconnect_output(self, slot):
        pass

    def validate_inouts(self):
        self.validate_inputs()
        self.validate_outputs()

    def validate(self):
        self.validate_inouts()
        self.state=Module.state_blocked

    def get_data(self, name):
        if name==Module.TRACE_SLOT:
            return self.tracer.df()
        elif name==Module.PARAMETERS_SLOT:
            return self._params
        return None

    def update_timestamps(self):
        return EMPTY_COLUMN

    def run_step(self,run_number,step_size,howlong):
        """Run one step of the module, with a duration up to the 'howlong' parameter.

        Returns a dictionary with at least 5 pieces of information: 1)
        the new state among (ready, blocked, terminated),2) a number
        of read items, 3) a number of updated items (written), 4) a
        number of created items, and 5) the effective number of steps run.
        """
        raise NotImplementedError('run_step not defined')

    def _return_run_step(self, next_state, steps_run, reads=0, updates=0, creates=0):
        assert next_state>=Module.state_ready and next_state<=Module.state_blocked
        if creates and updates==0:
            updates=creates
        elif creates > updates:
            raise ProgressiveError('More creates (%d) than updates (%d)', creates, updates)
        return {'next_state': next_state,
                'steps_run': steps_run,
                'reads': reads,
                'updates': updates,
                'creates': creates}

    def is_created(self):
        return self._state==Module.state_created

    def is_running(self):
        return self._state == Module.state_running

    def is_ready(self):
        if self.state == Module.state_terminated:
            logger.error("%s Not ready because it terminated", self.id())
            return False
        # source modules can be generators that
        # cannot run out of input, unless they decide so.
        if len(self._input_slots)==0:
            return True

        if self.state == Module.state_ready:
            return True

        if self.state == Module.state_blocked:
            zombie=True
            ready = True
            for slot in self.input_slot_values():
                if slot is None: # not required slot
                    continue
                in_module = slot.output_module
                in_ts = in_module.last_update()
                ts = self.last_update()
                if in_ts is None:
                    logger.info("%s Not ready because %s has not started", self.id(), in_module.id())
                    ready = False
                elif (ts is not None) and (in_ts <= ts):
                    logger.info("%s Not ready because %s is not newer", self.id(), in_module.id())
                    ready = False
                
                if in_module.state!=Module.state_terminated:
                    zombie = False
            if zombie:
                self.state = Module.state_terminated
            return ready
        logger.info("%s Not ready because is in weird state %s", self.id(), self.state_name[self.state])
        return False

    def is_terminated(self):
        return self._state==Module.state_terminated

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, s):
        self.set_state(s)

    def set_state(self, s):
        assert s>=Module.state_created and s<=Module.state_terminated, "State %s invalid in module %s"%(s, self.id())
        self._state = s

    def trace_stats(self, max_runs=None):
        return self.tracer.trace_stats(max_runs)

    def predict_step_size(self, duration):
        self.predictor.fit(self.trace_stats())
        return self.predictor.predict(duration, self.default_step_size)

    def start(self):
        pass

    def _stop(self, run_number):
        self._end_time = self._start_time
        self._last_update = run_number
        self._start_time = None
        assert self.state != self.state_running

    def end(self):
        pass

    def last_update(self):
        return self._last_update

    def last_time(self):
        return self._end_time

    def run(self, run_number):
        if self.is_running():
            raise ProgressiveError('Module already running')
        next_state = self.state
        exception = None
        now=self.timer()
        quantum=self.params.quantum
        tracer=self.tracer
        if quantum==0:
            quantum=0.1
            logger.error('Quantum is 0 in %s, setting it to a reasonable value', self.id())
        self.state = Module.state_running
        self._start_time = now
        self._end_time = self._start_time + quantum

        step_size = np.ceil(self.default_step_size*quantum)
        #TODO Forcing 4 steps, but I am not sure, maybe change when the predictor improves
        max_time = quantum / 4.0
        
        tracer.start_run(now,run_number)
        while self._start_time < self._end_time:
            remaining_time = self._end_time-self._start_time
            step_size = self.predict_step_size(np.min([max_time, remaining_time]))
            # Not sure...
            #if step_size == 0: 
            #    break
            run_step_ret = {'reads': 0, 'updates': 0, 'creates': 0}
            try:
                tracer.before_run_step(now,run_number)
                run_step_ret = self.run_step(run_number, step_size, remaining_time)
                next_state = run_step_ret['next_state']
                now = self.timer()
            except StopIteration:
                next_state = Module.state_terminated
                run_step_ret['next_state'] = next_state
                now = self.timer()
                break
            except Exception as e:
                next_state = Module.state_terminated
                run_step_ret['next_state'] = next_state
                now = self.timer()
                logger.debug("Exception in %s", self.id())
                tracer.exception(now,run_number)
                exception = e
                self._had_error = True
                self._start_time = now
                break
            finally:
                tracer.after_run_step(now,run_number,**run_step_ret)
                self.state = next_state
            if self._start_time is None or self.state != Module.state_ready:
                tracer.run_stopped(now,run_number)
                break
            self._start_time = now
        self.state=next_state
        if self.state==Module.state_terminated:
            tracer.terminated(now,run_number)
        tracer.end_run(now,run_number)
        self._stop(run_number)
        if exception:
            print_exc()
            raise exception



class Print(Module):
    def __init__(self, columns=None, **kwds):
        self._add_slots(kwds,'input_descriptors', [SlotDescriptor('inp')])
        super(Print, self).__init__(quantum=0.1, **kwds)
        self._columns = columns

    def run_step(self,run_number,step_size,howlong):
        df = self.get_input_slot('inp').data()
        steps=len(df)
        print df
        #print df.info()
        return self._return_run_step(Module.state_blocked, steps_run=len(df), reads=steps)

from inspect import getargspec
from traceback import print_exc
import re

import pandas as pd
import numpy as np

from progressivis.core.common import ProgressiveError, type_fullname
from progressivis.core.utils import (empty_typed_dataframe,
                                     typed_dataframe,
                                     DataFrameAsDict,
                                     remove_nan,
                                     force_valid_id_columns)
from progressivis.core.scheduler import Scheduler
from progressivis.core.slot import Slot, SlotDescriptor, InputSlots, OutputSlots
from progressivis.core.tracer import Tracer
from progressivis.core.time_predictor import TimePredictor
from progressivis.core.storagemanager import StorageManager

import logging
logger = logging.getLogger(__name__)


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

def slot_to_json(slot):
    if slot is None:
        return None
    if isinstance(slot, list):
        return [ slot_to_json(s) for s in slot]
    return slot.to_json()

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
    state_zombie = 4
    state_terminated = 5
    state_invalid = 6
    state_name = ['created', 'ready', 'running', 'blocked', 'zombie', 'terminated', 'invalid']

    def __init__(self,
                 id=None,
                 group=None,
                 scheduler=None,
                 tracer=None,
                 predictor=None,
                 storage=None,
                 input_descriptors=[],
                 output_descriptors=[],
                 **kwds):
        """Module(id=None,scheduler=None,tracer=None,predictor=None,storage=None,input_descriptors=[],output_descriptors=[])
        """
        if scheduler is None:
            scheduler = Scheduler.default
        if tracer is None:
            tracer = Tracer.default()
        if predictor is None:
            predictor = TimePredictor.default()
        if storage is None:
            storage = StorageManager.default
        if id is None:
            id = scheduler.generate_id(self.pretty_typename())

        predictor.id = id

        # always present
        output_descriptors = output_descriptors + [SlotDescriptor(Module.TRACE_SLOT, type=pd.DataFrame, required=False)]
        
        input_descriptors = input_descriptors + [SlotDescriptor(Module.PARAMETERS_SLOT, type=pd.DataFrame, required=False)]
        self._id = id
        self._group = group
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
        self._input_slots = self._validate_descriptors(input_descriptors)
        self.input_descriptors = {d.name: d for d in input_descriptors}
        self._output_slots = self._validate_descriptors(output_descriptors)
        self.output_descriptors = {d.name: d for d in output_descriptors}
        self.default_step_size = 1
        self.input = InputSlots(self)
        self.output = OutputSlots(self)
        self._scheduler.add_module(self)
        self._start_run = None
        self._end_run = None

    def destroy(self):
        self.scheduler().remove_module(self)

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

    @property
    def parameter(self):
        return self._params

    @property
    def lock(self):
        return self.scheduler().lock

    def _parse_parameters(self, kwds):
        self._params = self.create_dataframe(self.all_parameters + [self.UPDATE_COLUMN_DESC])
        self.params = DataFrameAsDict(self._params)
        for (name,dtype,dflt) in self.all_parameters:
            if name in kwds:
                self.params[name] = kwds[name]

    def timer(self):
        return self._scheduler.timer()

    def to_json(self, short=False):
        s = self.scheduler()
        json = {
            'is_running': s.is_running(),
            'is_terminated': s.is_terminated(),
            'run_number': s.run_number(),
            'id': self.id,
            'classname': self.pretty_typename(),
            'is_visualization': self.is_visualization(),
            'last_update': self._last_update,
            'state': self.state_name[self._state]
        }
        if short:
            return json
        
        json.update({
            'start_time': self._start_time,
            'end_time': self._end_time,
            'input_slots': { k: slot_to_json(s) for (k, s) in self._input_slots.iteritems() },
            'output_slots': { k: slot_to_json(s) for (k, s) in self._output_slots.iteritems() },
            'default_step_size': self.default_step_size,
            'parameters': self.remove_nan(self.current_params().to_dict())
        })
        return json

    @staticmethod
    def remove_nan(d):
        return remove_nan(d)

    def get_image(self, run_number=None):
        return None

    def describe(self):
        print 'id: %s' % self.id
        print 'class: %s' % type_fullname(self)
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
    
    def pretty_typename(self):
        name = self.__class__.__name__
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s1 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        s1 = re.sub('_module$', '', s1)
        return s1

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return u'Module %s: %s' % (self.__class__.__name__, self.id)

    def __repr__(self):
        return self.__unicode__()

    def __hash__(self):
        return self._id.__hash__()

    @property
    def id(self):
        return self._id

    @property
    def group(self):
        return self._group

    def scheduler(self):
        return self._scheduler

    def start(self):
        self.scheduler().start()

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
        return self.input_descriptors[name].type

    def input_slot_required(self,name):
        return self.input_descriptors[name].required

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
        valid = True
        for sd in self.input_descriptors.values():
            slot = self._input_slots[sd.name]
            if sd.required and slot is None:
                logger.error('Missing inputs slot %s in %s', sd.name, self._id)
                valid = False
        return valid

    def get_output_slot(self,name):
         # raise error is the slot is not declared
        return self._output_slots[name]

    def output_slot_type(self,name):
        return self.output_descriptors[name].type

    def output_slot_values(self):
        return self._output_slots.values()

    def output_slot_names(self):
        return self._output_slots.keys()

    def validate_outputs(self):
        valid = True
        for sd in self.output_descriptors.values():
            slots = self._output_slots[sd.name]
            if sd.required and (slots is None or len(slots)==0):
                logger.error('Missing required output slot %s in %s', sd.name, self._id)
                valid = False
            if slots:
                for slot in slots:
                    if not slot.validate_types():
                        valid = False
        return valid

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
        return self.validate_inputs() and self.validate_outputs()

    def validate(self):
        if self.validate_inouts():
            self.state=Module.state_blocked
            return True
        else:
            self.state=Module.state_invalid
            return False

    def get_data(self, name):
        if name==Module.TRACE_SLOT:
            return self.tracer.df()
        elif name==Module.PARAMETERS_SLOT:
            return self._params
        return None

    def update_timestamps(self):
        return Module.EMPTY_COLUMN

    def run_step(self,run_number,step_size,howlong):
        """Run one step of the module, with a duration up to the 'howlong' parameter.

        Returns a dictionary with at least 5 pieces of information: 1)
        the new state among (ready, blocked, zombie),2) a number
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

    def is_visualization(self):
        return False

    def get_visualization(self):
        return None

    def is_created(self):
        return self._state==Module.state_created

    def is_running(self):
        return self._state == Module.state_running

    def is_ready(self):
        if self.state == Module.state_terminated:
            logger.info("%s Not ready because it terminated", self.id)
            return False
        if self.state == Module.state_invalid:
            logger.info("%s Not ready because it is invalid", self.id)
            return False
        # source modules can be generators that
        # cannot run out of input, unless they decide so.
        if len(self._input_slots)==0:
            return True

        # Module is either a source or has buffered data to process
        if self.state == Module.state_ready:
            return True

        # Module is waiting for some input, test if some is available
        # to let it run. If all the input modules are terminated,
        # the module is blocked, cannot run any more, so it is terminated
        # too.
        if self.state == Module.state_blocked:
            slots = self.input_slot_values()
            in_count = 0
            term_count = 0
            ready_count = 0
            for slot in slots:
                if slot is None: # slot not required and not connected
                    continue
                in_count += 1
                in_module = slot.output_module
                in_ts = in_module.last_update()
                ts = self.last_update()

                if in_module.state==Module.state_terminated or in_module.state==Module.state_invalid:
                    term_count += 1
                elif (ts is None) or (in_ts > ts):
                    ready_count += 1
                
            if in_count != 0 and term_count==in_count: # if all the input slot modules are terminated or invalid
                logger.info('%s zombie', self.id)
                self.state = Module.state_zombie
                ready_count = 0
             # sources are always ready, and when 1 is ready, the module can run.
            return in_count==0 or ready_count!=0
        logger.error("%s Not ready because is in weird state %s", self.id, self.state_name[self.state])
        return False

    def cleanup_run(self, run_number):
        """Perform operations such as switching state from zombie to terminated.

        Resources could also be released for terminated modules.
        """
        if self.is_zombie(): # terminate modules that died in the previous run
            self.state = Module.state_terminated

    def is_zombie(self):
        return self._state==Module.state_zombie

    def is_terminated(self):
        return self._state==Module.state_terminated

    def is_valid(self):
        return self._state!=Module.state_invalid

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, s):
        self.set_state(s)

    def set_state(self, s):
        assert s>=Module.state_created and s<=Module.state_invalid, "State %s invalid in module %s"%(s, self.id)
        self._state = s

    def trace_stats(self, max_runs=None):
        return self.tracer.trace_stats(max_runs)

    def predict_step_size(self, duration):
        self.predictor.fit(self.trace_stats())
        return self.predictor.predict(duration, self.default_step_size)

    def starting(self):
        pass

    def _stop(self, run_number):
        self._end_time = self._start_time
        self._last_update = run_number
        self._start_time = None
        assert self.state != self.state_running
        self.end_run(run_number)

    def set_start_run(self, start_run):
        if start_run is None or callable(start_run):
            self._start_run = start_run
        else:
            raise ProgressiveError('value should be callable or None', start_run)

    def start_run(self, run_number):
        if self._start_run:
            self._start_run(self, run_number)

    def set_end_run(self, end_run):
        if end_run is None or callable(end_run):
            self._end_run = end_run
        else:
            raise ProgressiveError('value should be callable or None', end_run)

    def end_run(self, run_number):
        if self._end_run:
            self._end_run(self, run_number)

    def ending(self):
        pass

    def last_update(self):
        return self._last_update

    def last_time(self):
        return self._end_time

    def _update_params(self, run_number):
        pslot = self.get_input_slot(self.PARAMETERS_SLOT)
        if pslot is None or pslot.output_module is None: # optional slot
            return
        df = pslot.data()
        if df is None:
            return
        s2 = df.loc[df.index[-1]]
        s1 = self._params.loc[self._params.index[-1]]
        if s2[Module.UPDATE_COLUMN] <= s1[Module.UPDATE_COLUMN]:
            # no need to update
            return
        s3 = s2.combine_first(s1)
        s3[self.UPDATE_COLUMN] = run_number
        logger.info('Changing params of %s for:\n%s', self.id, s3)
        self._params.loc[self._params.index[-1]+1] = s3 # seems to drop undeclared columns

    def current_params(self):
        return self._params.loc[self._params.index[-1]]

    def set_current_params(self, v):
        if not isinstance(v,pd.Series):
            v = pd.Series(v, dtype=object) # raises error if not compatible
        with self.lock:
            current = self.current_params()
            v = current.combine_first(v) # fill-in missing values
            v[self.UPDATE_COLUMN] = self.scheduler.run_number()
            self._params.loc[self._params.index[-1]+1] = v
        return v

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
            logger.error('Quantum is 0 in %s, setting it to a reasonable value', self.id)
        self.state = Module.state_running
        self._start_time = now
        self._end_time = self._start_time + quantum

        self._update_params(run_number)

        #step_size = np.ceil(self.default_step_size*quantum)
        #TODO Forcing 4 steps, but I am not sure, maybe change when the predictor improves
        max_time = quantum / 4.0
        
        run_step_ret = {'reads': 0, 'updates': 0, 'creates': 0}
        self.start_run(run_number)
        tracer.start_run(now,run_number)
        while self._start_time < self._end_time:
            remaining_time = self._end_time-self._start_time
            if remaining_time <=0:
                logger.info('Late by %d s in module %s', remaining_time, self.pretty_typename())
                break # no need to try to squeeze anything
            logger.debug('Time remaining: %f in module %s', remaining_time, self.pretty_typename())
            step_size = self.predict_step_size(np.min([max_time, remaining_time]))
            logger.debug('step_size=%d in module %s', step_size, self.pretty_typename())
            if step_size == 0:
                logger.debug('step_size of 0 in module %s', self.pretty_typename())
                break
            try:
                tracer.before_run_step(now,run_number)
                run_step_ret = self.run_step(run_number, step_size, remaining_time)
                next_state = run_step_ret['next_state']
                now = self.timer()
            except StopIteration as e:
                #print_exc()
                logger.info('In Module.run(): Received a StopIteration exception')
                next_state = Module.state_zombie
                run_step_ret['next_state'] = next_state
                now = self.timer()
                break
            # except Exception as e:
            #     next_state = Module.state_zombie
            #     run_step_ret['next_state'] = next_state
            #     now = self.timer()
            #     logger.debug("Exception in %s", self.id)
            #     tracer.exception(now,run_number)
            #     exception = e
            #     self._had_error = True
            #     self._start_time = now
            #     break
            finally:
                assert run_step_ret is not None, "Error: %s run_step_ret not returning a dict" % self.pretty_typename()
                tracer.after_run_step(now,run_number,**run_step_ret)
                self.state = next_state
                logger.debug('Next step is %s in module %s', self.state_name[next_state], self.pretty_typename())
            if self._start_time is None or self.state != Module.state_ready:
                tracer.run_stopped(now,run_number)
                break
            self._start_time = now
        self.state=next_state
        if self.state==Module.state_zombie:
            logger.debug('Module %s zombie', self.pretty_typename())
            tracer.terminated(now,run_number)
        tracer.end_run(now,run_number)
        self.end_run(run_number)
        self._stop(run_number)
        if exception:
            print_exc()
            raise exception

    # Convenience methods
    @staticmethod
    def create_dataframe(columns, empty=False, types=None, values=None):
        if empty or (values is None and types is not None):
            return empty_typed_dataframe(columns, types)
        return typed_dataframe(columns, types, values)

    @staticmethod
    def last_row(df, remove_update=False):
        if df is None:
            return None
        index = df.index
        if len(index)==0:
            return None
        idx = index[-1]
        last = df.loc[idx]
        if remove_update:
            del last[Module.UPDATE_COLUMN]
        return last

    @staticmethod
    def add_row(df, row):
        index = df.index
        if len(index)==0:
            df.loc[0] = row
        else:
            df.loc[index[-1]+1] = row
        return df

    @staticmethod
    def force_valid_id_columns(df):
        force_valid_id_columns(df)

def print_len(x):
    if x is not None:
        print len(x)

class Every(Module):
    def __init__(self, proc=print_len, constant_time=True, **kwds):
        self._add_slots(kwds,'input_descriptors', [SlotDescriptor('inp')])
        super(Every, self).__init__(**kwds)
        self._proc = proc
        self._constant_time = constant_time

    def predict_step_size(self, duration):
        if self._constant_time:
            return 1
        return self(Every, self).predict_step_size(duration)

    def run_step(self,run_number,step_size,howlong):
        df = self.get_input_slot('inp').data()
        reads = 0
        if df is not None:
            reads=len(df)            
            with self.scheduler().stdout_parent():
                self._proc(df)
        return self._return_run_step(Module.state_blocked, steps_run=1, reads=reads)

def prt(x):
    print x

class Print(Every):
    def __init__(self, **kwds):
        super(Print, self).__init__(quantum=0.1, proc=prt, constant_time=True, **kwds)



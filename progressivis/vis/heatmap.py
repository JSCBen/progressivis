from progressivis.core.utils import indices_len
from progressivis.core.slot import SlotDescriptor
from progressivis.table import Table
from progressivis.table.module import TableModule


import numpy as np
import scipy as sp

from PIL import Image

import re

import logging
logger = logging.getLogger(__name__)


class Heatmap(TableModule):
    parameters = [('cmax', np.dtype(float), np.nan),
                  ('cmin', np.dtype(float), np.nan),
                  ('high', np.dtype(int),   65536),
                  ('low',  np.dtype(int),   0),
                  ('filename', np.dtype(object), None),
                  ('history', np.dtype(int), 3) ]

    # schema = [('image', np.dtype(object), None),
    #           ('filename', np.dtype(object), None),
    #           UPDATE_COLUMN_DESC]
    schema = "{filename: string, time: int64}"
                 
    def __init__(self, colormap=None, **kwds):
        self._add_slots(kwds,'input_descriptors',
                        [SlotDescriptor('array', type=Table)])
        super(Heatmap, self).__init__(table_slot='heatmap', **kwds)
        self.colormap = colormap
        self.default_step_size = 1

        name = self.generate_table_name('Heatmap')
        p = self.params
        if p.filename is None:
            p.filename = name+'%d.png'
        self._table = Table(name,
                            dshape=Heatmap.schema,
#                            scheduler=self.scheduler(),
                            create=True)

    def predict_step_size(self, duration):
        _ = duration
        # Module sample is constant time (supposedly)
        return 1

    def run_step(self,run_number,step_size,howlong):
        dfslot = self.get_input_slot('array')
        input_df = dfslot.data()
        dfslot.update(run_number, self.id)
        indices = dfslot.created.next()
        steps = indices_len(indices)
        if steps == 0:
            indices = dfslot.updated.next()
            steps = indices_len(indices)
            if steps==0:
                return self._return_run_step(self.state_blocked, steps_run=1)
        with dfslot.lock:
            histo = input_df.last()['array']
        if histo is None:
            return self._return_run_step(self.state_blocked, steps_run=1)
        p = self.params
        cmax = p.cmax
        if np.isnan(cmax):
            cmax = None
        cmin = p.cmin
        if np.isnan(cmin):
            cmin = None
        high = p.high
        low = p.low
        try:
            image = sp.misc.toimage(sp.special.cbrt(histo), cmin=cmin, cmax=cmax, high=high, low=low, mode='I')
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
            filename = p.filename
        except:
            image = None
            filename = None
        if filename is not None:
            try:
                if re.search(r'%(0[\d])?d', filename):
                    filename = filename % (run_number)
                filename = self.storage.fullname(self, filename)
                 #TODO should do it atomically since it will be called 4 times with the same fn
                image.save(filename, format='PNG', bits=16)
                logger.debug('Saved image %s', filename)
                image = None
            except:
                logger.error('Cannot save image %s', filename)
                raise

        if len(self._table)==0 or  self._table.last()['time'] != run_number:
            values = {'filename': filename, 'time': run_number}
            with self.lock:
                self._table.add(values)
        return self._return_run_step(self.state_blocked,
                                     steps_run=1,
                                     reads=1,
                                     updates=1)

    def is_visualization(self):
        return True

    def get_visualization(self):
        return "heatmap"

    def to_json(self, short=False):
        json = super(Heatmap, self).to_json(short)
        if short:
            return json
        return self.heatmap_to_json(json, short)

    def heatmap_to_json(self, json, short):
        dfslot = self.get_input_slot('array')
        histo = dfslot.output_module
        json['columns'] = [histo.x_column, histo.y_column]
        with dfslot.lock:
            histo_df = dfslot.data()
            if histo_df is not None and len(histo_df) != 0:
                row = histo_df.last()
                if not (np.isnan(row['xmin']) or np.isnan(row['xmax'])
                        or np.isnan(row['ymin']) or np.isnan(row['ymax'])):
                    json['bounds'] = {
                        'xmin': row['xmin'],
                        'ymin': row['ymin'],
                        'xmax': row['xmax'],
                        'ymax': row['ymax']
                    }
        with self.lock:
            df = self._table
            if df is not None and self._last_update != 0:
                row = df.last()
                json['image'] = "/progressivis/module/image/%s?run_number=%d"%(self.id,row['time'])
        return json

    def get_image(self, run_number=None):
        if self._table is None or len(self._table)==0:
            return None
        last = self._table.last()
        if run_number is None or run_number >= last['time']:
            run_number = last['time']
            filename = last['filename']
        else:
            time = self._table['time']
            idx = np.where(time==run_number)[0]
            if len(idx)==0:
                filename = last['filename']
            else:
                filename = self._table['filename'][idx[0]]

        return filename

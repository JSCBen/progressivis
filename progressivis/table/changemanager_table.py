from __future__ import absolute_import, division, print_function

from progressivis.core.changemanager_base import BaseChangeManager

from .table_base import BaseTable
from .tablechanges import TableChanges

class TableChangeManager(BaseChangeManager):
    """
    Manage changes that occured in a Table between runs.
    """
    def __init__(self,
                 slot,
                 buffer_created=True,
                 buffer_updated=False,
                 buffer_deleted=False,
                 manage_columns=True):
        super(TableChangeManager, self).__init__(
            slot,
            buffer_created,
            buffer_updated,
            buffer_deleted,
            manage_columns)
        data = slot.data()
        if data.changes is None:
            data.changes = TableChanges(slot.scheduler())

    def update(self, run_number, data, mid=None, cleanup=True):
        assert isinstance(data, BaseTable)
        if data is None or (run_number != 0 and run_number <= self._last_update):
            return
        #print('compute_updates(%s,%s,%d,%d)'%(data.name, mid, self._last_update, run_number))
        changes = data.compute_updates(self._last_update, mid, cleanup=cleanup)
        self._last_update = run_number
        self._row_changes.combine(changes,
                                  self.created.buffer,
                                  self.updated.buffer,
                                  self.deleted.buffer)

from ..core.slot import Slot
Slot.add_changemanager_type(BaseTable, TableChangeManager)

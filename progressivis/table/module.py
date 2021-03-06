"""
TableModule is the base class for all the modules updating internally a Table
and exposing it as an output slot.
"""

from __future__ import absolute_import, division, print_function

from ..core.module import Module
from ..core.slot import SlotDescriptor
from .table import Table

# pylint: disable=abstract-method
class TableModule(Module):
    "Base class for modules managing tables."
    def __init__(self, table_slot='table', columns=None, **kwds):
        self._add_slots(kwds, 'output_descriptors',
                        [SlotDescriptor(table_slot, type=Table, required=False)])
        super(TableModule, self).__init__(**kwds)
        self._columns = columns
        self._table_slot = table_slot
        self._table = None

    def table(self):
        "Return the table"
        return self._table

    def get_data(self, name):
        if name == self._table_slot:
            return self.table()
        return super(TableModule, self).get_data(name)

    def get_columns(self, df):
        """
        Return all the columns of interest from the specified table.

        If the module has been created without a list of columns, then all the columns
        of the table are returned.
        Otherwise, the interesection between the specified list and the existing columns
        is returned.
        """
        if df is None:
            return None
        if self._columns is None:
            self._columns = list(df.columns)
        else:
            cols = set(self._columns)
            diff = cols.difference(df.columns)
            for column in diff:
                self._columns.remove(column) # maintain the order
        return self._columns

    def filter_columns(self, df, indices=None):
        """
        Return the specified table filtered by the specified indices and limited to the
        columns of interest.
        """
        if self._columns is None:
            if indices is None:
                return df
            return df.loc[indices]
        cols = self.get_columns(df)
        if cols is None:
            return None
        if indices is None:
            return df[cols]
        return df.loc[indices, cols]

from . import ProgressiveTest
from time import sleep

from progressivis import Print, Scheduler
from progressivis.io import CSVLoader
from progressivis.stats import Min
from progressivis.datasets import get_dataset


class TestScheduler(ProgressiveTest):

    def test_scheduler(self):
        s = Scheduler()
        csv = CSVLoader(get_dataset('bigfile'),name="csv", index_col=False,header=None,scheduler=s)

        #smp = Sample(n=10,scheduler=s)
        #smp.input.df = csv.output.table

        self.assertIs(s["csv"], csv)
        csv.scheduler().start()

        sleep(1)
        self.assertTrue(csv.scheduler().is_running())

        #smp2 = Sample(n=15, scheduler=s)
        #smp2.input.df = csv.output.df

        def add_min():
            m = Min(scheduler=s)
            # Of course, sleeping here is a bad idea. this is to illustrate
            # that add_min will be executed atomically by the scheduler. 
            # using a sleep outside of add_oneshot_tick_proc would lead to an inconsistent
            # state.
            #sleep(1)
            m.input.table = csv.output.table
            prt = Print(proc=self.terse, scheduler=s)
            prt.input.df = m.output.table

        s.add_oneshot_tick_proc(add_min)

        sleep(1)
        #self.assertTrue(s._runorder.index(smp.id) > s._runorder.index(csv.id))
        #self.assertTrue(s._runorder.index(smp2.id) > s._runorder.index(csv.id))
        #self.assertTrue(s._runorder.index(m.id) > s._runorder.index(smp2.id))
        s.stop()
        s.join()

if __name__ == '__main__':
    ProgressiveTest.main()

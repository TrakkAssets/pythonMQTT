from datetime import datetime, timedelta

import threading

class TimeoutFunction:
    def __init__(self, func, milliseconds, *args):
        sec = 0.001 * milliseconds
        def func_wrapper():
            func(*args)
        self.t = threading.Timer(sec, func_wrapper)
        self.t.start()

    def cancel(self):
        self.t.cancel()

class IntervalFunction():
    sec = 30000
    running = False
    
    def __init__(self, func, milliseconds, *args):
        self.sec = 0.001 * milliseconds
        self.func = func
        self.args = args
        self._run()
    
    def _run(self):
        self.t = threading.Timer(self.sec, self._run)
        self.t.start()
        self.running = True
        self.func(*self.args)

    def interval(self, milliseconds):
        if(self.sec != 0.001 * milliseconds):
            self.sec = 0.001 * milliseconds
            self.t.cancel()
            self._run()

    def cancel(self):
        self.running = False
        self.t.cancel()
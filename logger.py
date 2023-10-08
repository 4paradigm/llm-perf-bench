#! /usr/bin/env python3

import pickle
import threading
from queue import Empty

class Logger(threading.Thread):
    def __init__(self, msg_queue, stop_event, log_file, pickle_protocol=3):
        self._msg_queue = msg_queue
        self._stop_event = stop_event
        self._log_file = log_file
        self._pickle_prot = pickle_protocol
        threading.Thread.__init__(self)

    def run(self):
        with open(self._log_file, 'wb') as f:
            while not self._stop_event.is_set():
                try:
                    msg = self._msg_queue.get(timeout=1)
                except Empty:
                    continue
                pickle.dump(msg, f, protocol=self._pickle_prot)
            msg = {"type": "exit", "data": {"reason": "stop_event"}}
            pickle.dump(msg, f, protocol=self._pickle_prot)
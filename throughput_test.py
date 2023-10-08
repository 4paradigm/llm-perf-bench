#! /usr/bin/env python3

import time
from executor import Executor
from logger import Logger
from simple_stats_display import SimpleStatsDisplay
from queue import Queue, Empty
from threading import Event

class LLMThroughputTest():
    def __init__(self, test_info):
        self._test_info = test_info
        self._initialize()

    def _initialize(self):
        # inter-thread message queues
        self._q_exec = Queue()
        self._q_logger = Queue()
        self._q_stat = Queue()
        # Threads related objects
        num_threads = self._test_info["num_threads"]
        self._se_exec = [Event() for x in range(num_threads)]
        self._se_logger = Event()
        self._se_stat = Event()
        # Threads
        self._thread_exec = self._create_executor_threads()
        output_dir = self._test_info["output_dir"]
        test_id = self._test_info["test_id"]
        output_file = '%s/%s-U%03d' % (output_dir, test_id, num_threads)
        self._thread_logger = Logger(self._q_logger, self._se_logger, output_file)
        self._thread_stats = SimpleStatsDisplay(self._q_stat, self._se_stat)

    def _check_key_metrics(self):
        stats = self._key_metrics
        if stats['num_queries'] < 1:
            return False
        if stats['num_failed_queries'] / stats['num_queries'] > 0.8:
            return False
        if stats["avg_queue_time"] > 100:
            return False
        if stats["avg_output_speed"] < 1:
            return False
        return True

    def _create_executor_threads(self):
        t_exec = []
        num_threads = self._test_info["num_threads"]
        for i in range(num_threads):
            thread_id = "T-%03d" % i
            test_set = self._test_info["test_set"]
            t_exec.append(Executor(thread_id, self._se_exec[i], test_set, self._q_exec))
        return t_exec

    def _start_all_threads(self):
        self._thread_logger.start()
        self._thread_stats.start()
        for t in self._thread_exec:
            t.start()

    def _stop_all_threads(self):
        self._se_stat.set()
        self._thread_stats.join(10)
        self._se_logger.set()
        self._thread_logger.join(10)
        for se in self._se_exec:
            se.set()
        ts = time.time()
        for t in self._thread_exec:
            timeout = int(max(120 + ts - time.time(), 1))
            t.join(timeout)

    def _main_execution_loop(self):
        ts_start = time.time()
        time_limit = self._test_info["time_limit"]
        while time.time() < ts_start + time_limit:
            try:
                exec_record = self._q_exec.get(timeout=1)
            except Empty:
                continue
            # logger
            msg_record = {"type": "record", "data": exec_record}
            self._q_logger.put(msg_record)
            # in-test stats
            self._q_stat.put(exec_record)

    def exec_test(self):
        msg_test_info = {"type": "test_info", "data": self._test_info}
        self._q_logger.put(msg_test_info)

        self._start_all_threads()
        self._main_execution_loop()
        self._stop_all_threads()
        
        self._key_metrics = self._q_stat.get_nowait()
        ret = {'test_success': True, 'pass_key_stats': self._check_key_metrics()}
        return ret

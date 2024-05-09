#! /usr/bin/env python3

import time
import datetime
import threading
from queue import Empty
from statistics import mean
from collections import deque

class SimpleStatsDisplay(threading.Thread):
    def __init__(self, rec_queue, stop_event, display_interval=30):
        self._queue = rec_queue
        self._stop_event = stop_event
        self._display_interval = display_interval
        self._ts_display = 0
        self._history = {"num_queries": 0, "num_failed_queries": 0, "active_threads": set(), "queries": deque()}
        threading.Thread.__init__(self)

    def _process_record(self, record):
        self._history["num_queries"] += 1
        if not record["success"]:
            self._history["num_failed_queries"] += 1
            print('    Query Failed: %s' % record["err_msg"])
        self._history['active_threads'].add(record["tid"])
        if record["success"]:
            query = {"time": time.time()}
            query['queue_time'] = record["ts_token"][0]
            total_time = record["ts_token"][-1]
            query['resp_len'] = sum(len(t) for t in record["tokens"])
            if len(record["tokens"]) > 1:
                output_time = total_time - query['queue_time']
            else:
                output_time = total_time
            query['output_speed'] = query['resp_len'] / output_time
            query['usage'] = False
            if (record['usage']):
                query['usage'] = True
                query["completion_tokens"] = record["completion_tokens"]
                query["prompt_tokens"] = record["prompt_tokens"]
                query['token_speed'] = query['completion_tokens'] / output_time
            queries = self._history["queries"]
            queries.append(query)
            while len(queries) > 500:
                queries.popleft()

    def _collect_key_metrics(self):
        ret = dict()
        ret["num_queries"] = self._history["num_queries"]
        ret["num_failed_queries"] = self._history["num_failed_queries"]
        queries = self._history["queries"]
        ret["avg_queue_time"] = mean(q["queue_time"] for q in queries) if queries else 0
        ret["avg_output_speed"] = mean(q["output_speed"] for q in queries) if queries else 0
        return ret

    def _print_stats_with_interval(self):
        if time.time() > self._ts_display + self._display_interval:
            self._print_stats()
            self._ts_display = time.time()

    def _print_stats(self):
        stats_str = datetime.datetime.now().strftime('%H:%M:%S ')
        num_active_threads = len(self._history["active_threads"])
        num_queries = self._history["num_queries"]
        num_failed_queries = self._history["num_failed_queries"]
        stats_str += '[并发] %d [问答/错误] %d/%d \n' % (num_active_threads, num_queries, num_failed_queries)
        queries = self._history["queries"]
        if len(queries) > 1:
            avg_queue_time = mean(q["queue_time"] for q in queries)
            avg_output_speed = mean(q["output_speed"] for q in queries)

            if (queries[0]["usage"]):
                ave_token_speed = mean(q["token_speed"] for q in queries)

                min_prompt_token = min(q["prompt_tokens"] for q in queries)
                ave_prompt_token = mean(q["prompt_tokens"] for q in queries)
                max_prompt_token = max(q["prompt_tokens"] for q in queries)

                min_completion_token = min(q["completion_tokens"] for q in queries)
                ave_completion_token = mean(q["completion_tokens"] for q in queries)
                max_completion_token = max(q["completion_tokens"] for q in queries)

                total_completion_token = sum(q["completion_tokens"] for q in queries)

            total_resp_len = sum(q["resp_len"] for q in queries)
            total_time = time.time() - queries[0]["time"]
            throughput = total_resp_len / total_time
            
            if (queries[0]["usage"]):
                throughput_token = total_completion_token / total_time
                throughput_str = '%.1f 字/秒 %.1f Token/秒' % (throughput, throughput_token) if total_time > 100 or len(queries) > 100 else '统计中'
                stats_str += '[平均延迟] \t %.1f秒 \n' % avg_queue_time
                stats_str += '[出字均速] \t 每秒%.1f字 \t 每秒%.1fToken \n' % (avg_output_speed, ave_token_speed)       
                stats_str += '[总吞吐] \t %s \n' % throughput_str
                stats_str += '[提示token数] \t min: %d \t ave: %d \t max: %d \n' % (min_prompt_token, ave_prompt_token, max_prompt_token)
                stats_str += '[生成token数] \t min: %d \t ave: %d \t max: %d \n' % (min_completion_token, ave_completion_token, max_completion_token)
            else:
                throughput_str = '%.1f 字/秒' % throughput if total_time > 100 or len(queries) > 100 else '统计中'
                stats_str += '[平均延迟] %.1f秒 [出字均速] 每秒%.1f字 ' % (avg_queue_time, avg_output_speed)
                stats_str += '[总吞吐] %s' % throughput_str

        print(stats_str)

    def run(self):
        while not self._stop_event.is_set():
            self._print_stats_with_interval()
            try:
                record = self._queue.get(timeout=1)
            except Empty:
                continue
            self._process_record(record)
        self._queue.put(self._collect_key_metrics())

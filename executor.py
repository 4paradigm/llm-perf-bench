#! /usr/bin/env python3

import time
import datetime
import threading
from model_query import FailedQueryError, query_model

class Executor(threading.Thread):
    def __init__(self, thread_id, stop_event, workload, ret_queue):
        self._thread_id = thread_id
        self._stop_event = stop_event
        self._workload = workload
        self._queue = ret_queue
        self._query_model_func = query_model
        threading.Thread.__init__(self)
    
    def _exec_query(self, prompt, max_resp_tokens):
        ret = { "tid": self._thread_id }
        ret["prompt"] = prompt
        ret["max_resp_tokens"] = max_resp_tokens
        
        ts = time.time()
        ret["time"] = datetime.datetime.fromtimestamp(ts)
        ret["ts_token"] = []
        ret["tokens"] = []
        try:
            for token in self._query_model_func(prompt, max_resp_tokens):
                if not isinstance(token, str):
                    raise FailedQueryError("tokens should be strings")
                ret["ts_token"].append(time.time() - ts)
                ret["tokens"].append(token)
            if not ret["tokens"]:
                raise FailedQueryError("response without valid token")
            ret["success"] = True
        except FailedQueryError as e:
            ret["success"] = False
            ret["err_msg"] = e.get_err_msg()

        return ret

    def _run_random_testset(self):
        import random

        testset = self._workload["samples"]
        while not self._stop_event.is_set():
            prompt, max_resp_tokens = random.choice(testset)
            query_record = self._exec_query(prompt, max_resp_tokens)
            self._queue.put(query_record)
            if not query_record["success"]:
                time.sleep(1)

    def _run_conversation_dir(self):
        samples = self._workload["samples"]
        if not samples:
            return

        sample_idx = 0
        while not self._stop_event.is_set():
            sample = samples[sample_idx]
            prompt = sample["prompt"]
            max_resp_tokens = sample["max_resp_tokens"]
            query_record = self._exec_query(prompt, max_resp_tokens)
            query_record["conversation_file"] = sample.get("conversation_file")
            query_record["conversation_sample_index"] = sample.get("conversation_sample_index")
            self._queue.put(query_record)
            if not query_record["success"]:
                time.sleep(1)

            sample_idx = (sample_idx + 1) % len(samples)
    
    def run(self):
        mode = self._workload["mode"]
        if mode == "conversation_dir":
            self._run_conversation_dir()
            return
        self._run_random_testset()

if __name__ == '__main__':
    prompt, max_resp_tokens = ('晚上睡不着应该怎么办', 512)
    executor = Executor('offline-executor-thread', None, None, None)
    record = executor._exec_query(prompt, max_resp_tokens)
    print(''.join(record["tokens"]))
    print(record)

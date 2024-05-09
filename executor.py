#! /usr/bin/env python3

import time
import random
import datetime
import threading
from model_query import FailedQueryError, query_model

class Executor(threading.Thread):
    def __init__(self, thread_id, stop_event, testset, ret_queue):
        self._thread_id = thread_id
        self._stop_event = stop_event
        self._testset = testset
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
        ret["usage"] = False
        try:
            for token, usage in self._query_model_func(prompt, max_resp_tokens):
                if not isinstance(token, str):
                    raise FailedQueryError("tokens should be strings")
                ret["ts_token"].append(time.time() - ts)
                ret["tokens"].append(token)
                if (usage):
                    ret['usage'] = True
                    ret["completion_tokens"] = usage.completion_tokens
                    ret["total_tokens"] = usage.total_tokens
                    ret["prompt_tokens"] = usage.prompt_tokens
            if not ret["tokens"]:
                raise FailedQueryError("response without valid token")
            ret["success"] = True
        except FailedQueryError as e:
            ret["success"] = False
            ret["err_msg"] = e.get_err_msg()

        return ret
    
    def run(self):
        while not self._stop_event.is_set():
            prompt, max_resp_tokens = random.choice(self._testset)
            query_record = self._exec_query(prompt, max_resp_tokens)
            self._queue.put(query_record)
            if not query_record["success"]:
                time.sleep(1)

if __name__ == '__main__':
    prompt, max_resp_tokens = ('晚上睡不着应该怎么办', 512)
    executor = Executor('offline-executor-thread', None, None, None)
    record = executor._exec_query(prompt, max_resp_tokens)
    print(''.join(record["tokens"]))
    print(record)

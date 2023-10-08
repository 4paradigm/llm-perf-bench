#! /usr/bin/env python3

import re
import time
import json
import argparse
import subprocess
from math import ceil
from pathlib import Path
from datetime import datetime
from throughput_test import LLMThroughputTest

def gen_test_runs():
    num_threads = 1
    while num_threads < 1024:
        yield num_threads
        num_threads = max(num_threads + 3, ceil(num_threads * 1.2))

def gen_test_id(test_name):
    test_name = re.sub(r"\s+", '_', test_name)
    test_id = "%s-%s" % (test_name, datetime.now().strftime('%Y%m%d%H%M%S'))
    return test_id

def parse_testset(test_set_path):
    test_set = []
    with open(test_set_path, 'r') as f:
        for line in f:
            sp_line = line.split('|', 1)
            if len(sp_line) == 2 and sp_line[0].isdigit():
                prompt, resp_max_tokens = sp_line[1], int(sp_line[0])
            else:
                prompt, resp_max_tokens = line, 512
            test_set.append((prompt, resp_max_tokens))
    return test_set

def run_test(test_info):
    throughput_test = LLMThroughputTest(test_info)
    ret = throughput_test.exec_test()
    return ret

def main(test_name, test_description, test_set_path, working_dir, test_duration, test_runs):
    test_info = { "time": datetime.now() }
    test_info["test_description"] = test_description
    test_info["test_id"] = gen_test_id(test_name)
    test_info["test_set"] = parse_testset(test_set_path)
    test_info["time_limit"] = test_duration
    test_info["working_dir"] = working_dir.resolve()
    test_info["test_runs"] = test_runs if test_runs else list(gen_test_runs())
    output_dir_base = test_info["working_dir"] / 'output'
    output_dir_base.mkdir(exist_ok=True)
    test_info['output_dir'] = output_dir_base / test_info["test_id"]
    test_info['output_dir'].mkdir()
    benchmark_ver = subprocess.check_output(['git', 'describe', '--tags', '--dirty', '--long']).decode('ascii').strip()
    test_info['benchmark_ver'] = benchmark_ver
    args_str = json.dumps(test_info, default=str, ensure_ascii=False)

    print('[INFO] LLM throughput benchmark. Args %s\n' % args_str)
    for test_no, num_threads in enumerate(test_info["test_runs"], 1):    
        test_info['num_threads'] = num_threads
        print('[INFO] test-%d/%d: Starting test run...' % (test_no, len(test_info["test_runs"])))
        print('[INFO] LLM throughput test started with %d thread(s)' % test_info["num_threads"])
        print('[INFO] Test time is set to %d seconds' % test_info["time_limit"])
        test_result = run_test(test_info)
        print('[INFO] LLM throughput test exited\n')
        if not test_result['pass_key_stats']:
            print('[WARNING] Test failed on key metrics, benchmark will exit now.')
            break
        time.sleep(10)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', dest='test_name', help='identifier of the benchmark',
                        type=str, default = "llm benchmark")
    parser.add_argument('--desc', dest='test_description', help='description of this benchmark run',
                        type=str, default = "None")
    parser.add_argument('--work-dir', dest='work_dir', help='working directory',
                        type=Path, default = "./")
    parser.add_argument('--test-set', dest='test_set_path', help='path of the testset for llm test',
                        type=Path, default = "./resources/testset.txt")
    parser.add_argument('--test-duration', dest='test_duration', help='length of each test run in seconds',
                        type=int, default = 1800)
    parser.add_argument('--test-runs', dest='num_users', nargs='+', help='list of concurrent users for each test run',
                        type=int, default = None)
    args = parser.parse_args()
    main(args.test_name, args.test_description, args.test_set_path, args.work_dir, args.test_duration, args.num_users)

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
    if test_set_path.is_dir():
        return {
            "mode": "conversation_dir",
            "samples": parse_conversation_dir(test_set_path),
        }

    test_set = []
    with open(test_set_path, 'r') as f:
        for line in f:
            sp_line = line.split('|', 1)
            if len(sp_line) == 2 and sp_line[0].isdigit():
                prompt, resp_max_tokens = sp_line[1], int(sp_line[0])
            else:
                prompt, resp_max_tokens = line, 512
            test_set.append((prompt, resp_max_tokens))
    return {"mode": "random_testset", "samples": test_set}


def normalize_content(content):
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in (None, "text", "input_text"):
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        merged = '\n'.join(p for p in parts if p.strip())
        return merged or None
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text:
            return text
    return str(content)


def normalize_messages(raw_messages):
    messages = []
    for raw in raw_messages:
        if not isinstance(raw, dict):
            continue
        role = raw.get("role")
        if role not in {"system", "user", "assistant"}:
            continue
        content = normalize_content(raw.get("content"))
        if not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def parse_conversation_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        data = json.load(f)

    samples = []
    if not isinstance(data, list):
        return samples

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        messages = normalize_messages(item.get("messages") or [])
        if not messages:
            continue
        parameters = item.get("parameters") or {}
        max_tokens = parameters.get("max_tokens")
        if max_tokens is None:
            max_tokens = parameters.get("max_completion_tokens")
        if max_tokens is None:
            max_tokens = 512
        samples.append({
            "prompt": json.dumps(messages, ensure_ascii=False),
            "max_resp_tokens": int(max_tokens),
            "conversation_file": str(file_path),
            "conversation_sample_index": idx,
        })

    return samples


def parse_conversation_dir(test_set_path):
    samples = []
    for file_path in sorted(test_set_path.glob("*.json")):
        samples.extend(parse_conversation_file(file_path))
    return samples

def run_test(test_info):
    throughput_test = LLMThroughputTest(test_info)
    ret = throughput_test.exec_test()
    return ret

def main(test_name, test_description, test_set_path, working_dir, test_duration, test_runs):
    test_info = { "time": datetime.now() }
    test_info["test_description"] = test_description
    test_info["test_id"] = gen_test_id(test_name)
    test_info["test_set"] = parse_testset(test_set_path)
    test_info["test_set_size"] = len(test_info["test_set"]["samples"])
    test_info["time_limit"] = test_duration
    test_info["working_dir"] = working_dir.resolve()
    test_info["test_runs"] = test_runs if test_runs else list(gen_test_runs())
    output_dir_base = test_info["working_dir"] / 'output'
    output_dir_base.mkdir(exist_ok=True)
    test_info['output_dir'] = output_dir_base / test_info["test_id"]
    test_info['output_dir'].mkdir()
    try:
        benchmark_ver = subprocess.check_output(
            ['git', 'describe', '--tags', '--dirty', '--long'],
            stderr=subprocess.DEVNULL,
        ).decode('ascii').strip()
    except subprocess.CalledProcessError:
        benchmark_ver = "unknown"
    test_info['benchmark_ver'] = benchmark_ver
    args_str = json.dumps(test_info, default=str, ensure_ascii=False)

    print('[INFO] LLM throughput benchmark. Args %s\n' % args_str[:10000])
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

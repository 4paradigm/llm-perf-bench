## 关于llm-perf-benchmark

llm-perf-benchmark 是一个针对大语言模型多用户推理服务的性能测试工具。

### 使用方法

1. 编写接口函数query_model()

使用项目提供的模板model_query.py.template，并针对所测试的大语言模型进行修改
   ```sh
   cp model_query.py.template model_query.py
   vim model_query.py
   ```

当前仓库已经提供了一个可直接使用的 `model_query.py`，默认行为是：

- 优先调用 `BASE_URL/v1/messages`
- 如果接口不可用，自动回退到 `BASE_URL/v1/chat/completions`
- 输入可以是普通文本，也可以是标准 `messages` JSON 字符串

常用环境变量：

```sh
export LLM_PERF_BASE_URL=http://172.28.22.23:8888
export LLM_PERF_MODEL=qwen
```

2. 执行python3 llm_benchmark.py启动测试
   ```sh
   python3 llm_benchmark.py --name sagegpt_test --desc "Test SageGPT on 2x4PD AccXPU with TGI 1.0.3" --work-dir ./ --test-set ./resources/testset.txt
   ```

详细参数列表请参照：

   ```sh
   usage: llm_benchmark.py [-h] [--name TEST_NAME] [--desc TEST_DESCRIPTION]
                           [--work-dir WORK_DIR] [--test-set TEST_SET_PATH]
                           [--test-duration TEST_DURATION]
                           [--test-runs NUM_USERS [NUM_USERS ...]]

   options:
     -h, --help            show this help message and exit
     --name TEST_NAME      identifier of the benchmark
     --desc TEST_DESCRIPTION
                           description of this benchmark run
     --work-dir WORK_DIR   working directory
     --test-set TEST_SET_PATH
                           path of the testset for llm test
     --test-duration TEST_DURATION
                           length of each test run in seconds
     --test-runs NUM_USERS [NUM_USERS ...]
                           list of concurrent users for each test run
   ```

#### 普通 testset 模式

`--test-set` 指向一个文本文件时，行为不变：

- 每行一条请求
- 支持 `max_tokens|prompt`
- 多并发下随机抽样发送

#### 目录数据集模式

`--test-set` 也可以直接指向一个目录。目录下每个 `*.json` 文件会被读取，提取其中的 `messages` 和 `parameters`：

- 先按文件名排序
- 再按文件内记录顺序展开成一个总请求序列
- 然后按并发数把这个总序列切成多份连续 shard
- 每个线程顺序发送自己那一份

这意味着：

- 单个线程内部顺序稳定
- 全局发送顺序会因为并发而交错

目录模式示例：

```sh
cd llm-perf-bench
LLM_PERF_BASE_URL=http://172.28.22.23:8888 \
LLM_PERF_MODEL=qwen \
python3 -B llm_benchmark.py \
  --test-set ./dataset-20260327 \
  --test-duration 30 \
  --test-runs 4
```

如果环境变量已经提前设置，命令可以进一步简化为：

```sh
cd llm-perf-bench
python3 -B llm_benchmark.py --test-set ./dataset-20260327 --test-duration 30 --test-runs 4
```

3. 运行工具后将记录以下关键指标：

   [并发]： 当前测试的并发用户数。

   [问答/错误]： 对于已经发送的请求，记录当前累计收到的答复数以及累计收到的错误答复或者答复超时的数量。

   [平均延迟]： 记录当前系统的平均响应延迟。

   [出字均速]： 记录系统生成文本的平均速度，即每秒钟生成的字符数。

   [总吞吐]： 统计系统的总体性能，表示每秒钟能够生成的总字符数。

   ```sh
   23:16:06 [并发] 1 [问答/错误] 3/0 [平均延迟] 0.1秒 [出字均速] 每秒56.4字 [总吞吐] 59.5 字/秒
   ```


4. 对应输出的测试结果在$work_dir/output目录下

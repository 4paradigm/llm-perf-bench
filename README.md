## 关于llm-perf-benchmark

llm-perf-benchmark 是一个针对大语言模型多用户推理服务的性能测试工具。

### 使用方法

1. 编写接口函数query_model()

使用项目提供的模板model_query.py.template，并针对所测试的大语言模型进行修改
   ```sh
   cp model_query.py.template model_query.py
   vim model_query.py
   ```

2. 执行python3 llm_benchmark.py启动测试
   ```sh
   python3 llm_benchmark.py --name sagegpt_test --desc "Test SageGPT on 2x4PD AccXPU with TGI 1.0.3" --work-dir ./ --test-set ./resources/testset.txt
   ```

3. 收集$work_dir/output目录下输出的测试结果

4. 运行分析工具，生成报告


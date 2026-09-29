# Stage 4 接入包

把本目录中的 `stage4/` 复制到现有仓库根目录即可。

## Windows CMD

```bat
python -m pip install -r requirements-stage4.txt
python -m pytest stage4\tests -q
python -m stage4.cli --session demo-stage4 --query "根据候选人的 Redis 项目继续追问缓存击穿"
python -m pytest stage1\tests stage2\tests stage3\tests stage4\tests -q
```

其中 `stage4/agent_runtime/memory_runtime.py` 是 Stage4 与前面 Agent Runtime 的接入层；现有 Stage1/2/3 不需要重写。

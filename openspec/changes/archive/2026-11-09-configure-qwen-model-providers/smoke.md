# 百炼手动 smoke

自动化测试使用模拟传输。真实百炼请求的结果见文末。

1. 仅在本地文件缺失时，从 `config/project.template.json` 和 `config/user.project.template.json` 分别复制出 `config/project.json` 和 `config/user.project.json`。
2. 在被 Git 忽略的 `config/user.project.json` 填入 `llm.apiKey`。如需更换地域，覆盖 `llm.baseUrl` 和 `llm.rerankUrl`。早于 P06 的本地配置可从模板补入端点和 `modelCapabilities`，并将空的 `llm.provider` 更新为 `qwen`。
3. 在 PowerShell 的 `apps/backend` 目录执行下面的探测。成功时检查三条结果的模型、端点和毫秒延迟。

```powershell
uv run --locked python -c "
import asyncio
from super_ai.llm_provider import create_llm_provider
from super_ai.project_config import load_project_config

async def main():
    async with create_llm_provider(load_project_config()) as provider:
        print(await provider.readiness('chat'))
        print(await provider.readiness('embedding'))
        print(await provider.readiness('rerank'))

asyncio.run(main())
"
```

参考 [百炼重排 API](https://www.alibabacloud.com/help/en/model-studio/text-rerank-api) 和 [qwen3.7-max 模型参数](https://www.alibabacloud.com/help/en/model-studio/qwen3-7-max)。

## 真实百炼验收结果

2026-11-09（北京时间），直接加载本机 project.json 和 user.project.json，向百炼北京端点发起三项异步就绪探测。

| 能力 | 模型 | 结果 | 耗时或诊断 |
| --- | --- | --- | --- |
| chat | qwen3.7-max | 通过 | 2032 ms |
| embedding | text-embedding-v4 | 通过 | 629 ms |
| rerank | qwen3-vl-rerank | 通过 | 2297 ms |

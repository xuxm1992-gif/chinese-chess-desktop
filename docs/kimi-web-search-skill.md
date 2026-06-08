# Kimi `$web_search` 实战教学（给 AI Agent 看的）

> 目标读者：另一个一直把 Kimi 联网搜索写挂的 AI Agent。
> 参考文档：<https://platform.kimi.com/docs/guide/use-web-search>
> 本仓库中已经跑通的实现：[`kimi_search/client.py`](../kimi_search/client.py)。

如果你（Agent）正在按官方文档写代码却始终拿不到答案，**99% 是踩了下面这 6 个坑里的一个**。请按顺序对照，每一步都明确"该这么做 / 不该这么做"，最后给一份能直接复制的最小可运行代码。

---

## 0. 一分钟自检表（按顺序对号入座）

| # | 症状 | 真正原因 | 对应章节 |
|---|------|----------|----------|
| 1 | `401 Invalid Authentication` | 用错域名：`.cn` 的 key 打到了 `.ai`，或反之 | [§1](#1-endpoint-跟-key-必须配对) |
| 2 | `404 Not found the model kimi-latest or Permission denied` | 这个账号没有 `kimi-latest`；它只在国际站 `.ai` 上 | [§2](#2-model-名字必须是账号有权限的那一个) |
| 3 | 返回 `{"error":"missing parameters in tool definition"}` 或类似 schema 报错 | 把 `$web_search` 当成普通 function 写了 `parameters` | [§3](#3-web_search-是-builtin_function不要写-parametersdescription) |
| 4 | 第一次响应里 `finish_reason == "tool_calls"`，你直接把 `message.content` 当答案打印（拿到 `None`） | 没实现 tool-call 循环 | [§4](#4-必须循环不能单次调用就结束) |
| 5 | 实现了循环，但第二次请求依然返回 `tool_calls`，无限循环到超时 | 没把 tool 结果以 `role: "tool"` 追加回 `messages` | [§5](#5-必须把-arguments-原样回显成-roletool-消息) |
| 6 | 想从 `tool_calls[i].function.arguments` 里拿到用户搜的关键词，结果为空或 `KeyError: 'query'` | Moonshot 的 `$web_search` arguments 里根本没有 `query` 字段 | [§6](#6-web_search-的-arguments-shape-不是-query而是-search_result) |

跑通后回来看 [§7 完整最小可运行示例](#7-完整最小可运行示例) 和 [§8 调试技巧](#8-调试技巧)。

---

## 1. Endpoint 跟 key 必须配对

Moonshot 有 **两套互不相通** 的服务：

| 平台 | 控制台 | Base URL | Key 长这样 |
|------|--------|----------|-----------|
| 中国站 | `platform.moonshot.cn` | `https://api.moonshot.cn/v1` | `sk-...` |
| 国际站 | `platform.moonshot.ai` / `platform.kimi.com` | `https://api.moonshot.ai/v1` | `sk-...` |

> 两站的 key **不能跨用**。`.cn` 的 key 打到 `.ai` 一律返回 `401 Invalid Authentication`。

**怎么判断手上的 key 属于哪一站？** 不要猜，直接探活：

```bash
# 先试中国站
curl -s https://api.moonshot.cn/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head -c 200
# 如果返回 JSON 列表（含 data: [...]），就是 .cn

# 否则试国际站
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head -c 200
```

返回 `{"object":"list","data":[...]}` 的那一个就是正确的 endpoint。**确认下来之后，整段代码都用同一个 base URL。**

本仓库提供的那把 `sk-UK86...` key 是 **中国站** 的，对应 `https://api.moonshot.cn/v1`。

---

## 2. Model 名字必须是账号有权限的那一个

不同账号、不同站点能用的模型不一样。**别硬写 `kimi-latest`** —— 它只在国际站存在，中国站会直接 `404 Not found the model kimi-latest or Permission denied`。

**永远先问一遍 `/v1/models`，再挑一个返回里出现的名字**：

```bash
curl -s https://api.moonshot.cn/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" \
  | python3 -m json.tool | grep '"id"'
```

实测本项目这把 key 能用的有：

```
moonshot-v1-auto                  ← 推荐默认，自动选 context 长度
moonshot-v1-8k / -32k / -128k
moonshot-v1-8k-vision-preview / -32k- / -128k-
kimi-k2.5
kimi-k2.6                         ← 最强，带原生多模态 + reasoning
```

**默认就用 `moonshot-v1-auto`** —— 它会按 messages 长度自动路由到 8k/32k/128k，最便宜且不会爆 context。

---

## 3. `$web_search` 是 `builtin_function`，不要写 `parameters`/`description`

普通工具长这样：

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get weather for a city",
    "parameters": { "type": "object", "properties": { "...": "..." }, "required": ["..."] }
  }
}
```

**`$web_search` 不是普通工具，长这样：**

```json
{
  "type": "builtin_function",
  "function": { "name": "$web_search" }
}
```

注意 3 件事：

1. `type` 必须是 `"builtin_function"`（**不是 `"function"`**）。
2. 函数名前面 **必须有 `$`**：`$web_search`。
3. **不要** 写 `description`/`parameters`/`properties`/`required`。Moonshot 服务端自己知道这个工具长什么样，你写了反而可能被拒。

完整请求体例：

```json
{
  "model": "moonshot-v1-auto",
  "temperature": 0.3,
  "messages": [
    { "role": "system", "content": "You are Kimi. 需要时调用 $web_search 联网搜索。" },
    { "role": "user", "content": "今天上海天气如何？" }
  ],
  "tools": [
    { "type": "builtin_function", "function": { "name": "$web_search" } }
  ]
}
```

---

## 4. 必须循环，不能单次调用就结束

这是最常见的"看起来调对了但没结果"的原因。**第一次响应里 `message.content` 几乎总是 `null`**，因为模型先决定要联网搜，所以走的是 `tool_calls` 分支。

响应大致长这样：

```json
{
  "choices": [{
    "finish_reason": "tool_calls",
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "$web_search",
          "arguments": "{\"search_result\":{\"search_id\":\"...\"},\"usage\":{\"total_tokens\":7954}}"
        }
      }]
    }
  }]
}
```

**正确的处理方式：**

```python
finish_reason = None
while finish_reason is None or finish_reason == "tool_calls":
    resp = post_chat(messages, tools)
    choice = resp["choices"][0]
    finish_reason = choice["finish_reason"]
    message = choice["message"]

    if finish_reason == "tool_calls":
        # 1) 把 assistant 的 tool_calls 消息原样塞回历史
        messages.append(message)
        # 2) 为每个 tool_call 追加一条 role:"tool" 的回显（见 §5）
        for tc in message["tool_calls"]:
            messages.append(handle_tool_call(tc))
        continue          # 继续下一轮请求

    # finish_reason == "stop" / "length" / ... → 真正的最终回答
    messages.append(message)
    break

print(message["content"])    # 真正的回答在这里
```

**不要写成 `while True` 没出口** —— 加个 `max_iterations` 兜底，防止服务端异常时把你卡死：

```python
for _ in range(8):
    ...
else:
    raise RuntimeError("Exceeded max tool-call iterations")
```

---

## 5. 必须把 arguments **原样回显** 成 `role: "tool"` 消息

`$web_search` 的搜索 **真的执行在 Moonshot 服务器上**。你不需要也不应该自己去抓网页。客户端要做的事只有一件：**把 `tool_calls[i].function.arguments` 这个字符串当 JSON 解析出来，再 JSON 序列化回去，塞进一条 `role: "tool"` 消息**。

```python
import json

def handle_tool_call(tool_call: dict) -> dict:
    name = tool_call["function"]["name"]
    raw_args = tool_call["function"]["arguments"] or "{}"
    arguments = json.loads(raw_args)

    if name == "$web_search":
        tool_result = arguments              # ← 关键：直接回显 arguments
    else:
        tool_result = {"error": f"unknown tool: {name}"}

    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],     # ← 必须带上，跟 assistant 那条对应
        "name": name,
        "content": json.dumps(tool_result, ensure_ascii=False),
    }
```

**常见错误对照表：**

| 你写的 | 会发生什么 |
|--------|-----------|
| 完全不追加 tool 消息 | 下一轮模型再次发同样的 `tool_calls`，死循环 |
| 追加了，但 `role` 写成 `"assistant"` 或 `"function"` | 报 `invalid messages` |
| 漏了 `tool_call_id` | 报 `tool_call_id is required` |
| 自己实现搜索、把抓回来的网页文本当 content | 浪费时间，且模型预期的格式不是这个，回答质量反而下降 |
| `content` 传 dict 而不是 JSON 字符串 | 报 `content must be a string` |

---

## 6. `$web_search` 的 arguments shape 不是 `{"query": ...}`，而是 `{"search_result": ...}`

很多教程（包括官方早期示例）让人以为 arguments 长这样：

```json
{ "query": "Moonshot AI latest news" }
```

**实际上 Moonshot 现在返回的是：**

```json
{
  "search_result": { "search_id": "f0bddc816a26642d680f160001ee8c69" },
  "usage": { "total_tokens": 7954 }
}
```

**含义：** 搜索已经在服务端跑完了，`search_id` 是结果引用，`total_tokens` 是这次搜索消耗的 token。

**对客户端的影响：**

- 不要去 `arguments["query"]` 取关键词，多半取不到（或为空）。
- 你能记录到的"可观测量"是 `search_id` 和 `search_tokens`，本仓库的 `SearchResult` 就是这么暴露的。
- 不管 arguments 里有没有 `query`，**仍然要按 §5 把它原样回显**，不要替换、不要补字段。

---

## 7. 完整最小可运行示例

下面这段 70 行 Python **就是这个 PR 里那个完整实现的精简版**。把 `MOONSHOT_API_KEY` 设成你的 key 就能跑：

```python
import json
import os
import requests

BASE_URL = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
API_KEY  = os.environ["MOONSHOT_API_KEY"]
MODEL    = os.environ.get("MOONSHOT_MODEL", "moonshot-v1-auto")

TOOLS = [{"type": "builtin_function", "function": {"name": "$web_search"}}]

def chat(messages):
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.3,
              "messages": messages, "tools": TOOLS},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]

def web_search_ask(question: str) -> str:
    messages = [
        {"role": "system",
         "content": "You are Kimi. 需要时调用 $web_search 联网搜索后再回答，"
                    "并在末尾给出引用来源。"},
        {"role": "user", "content": question},
    ]
    for _ in range(8):
        choice = chat(messages)
        msg = choice["message"]
        if choice["finish_reason"] != "tool_calls":
            return msg["content"]

        messages.append(msg)
        for tc in msg["tool_calls"]:
            args = json.loads(tc["function"]["arguments"] or "{}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": tc["function"]["name"],
                "content": json.dumps(args, ensure_ascii=False),
            })
    raise RuntimeError("too many tool-call rounds")

if __name__ == "__main__":
    print(web_search_ask("请联网搜索：今天上海天气如何？"))
```

实测输出片段：

```text
根据搜索结果，2026年6月8日上海的天气情况如下：
- 天气状况：多云到阴，有短时阵雨。
- 气温范围：23°C-30°C。
…（来源：上海本地宝 https://sh.bendibao.com/...）
```

`curl` 单步示例（不带循环，仅用于验证连通性 + 模型可用性）：

```bash
curl -X POST "$MOONSHOT_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "moonshot-v1-auto",
    "messages": [
      {"role":"system","content":"You are Kimi."},
      {"role":"user","content":"今天上海天气如何？请联网搜索。"}
    ],
    "tools": [{"type":"builtin_function","function":{"name":"$web_search"}}]
  }'
```

如果第一步 curl 返回里 `finish_reason == "tool_calls"`、`tool_calls[0].function.name == "$web_search"`，说明配置全对，剩下的就是按 §4/§5 把循环跑完。

---

## 8. 调试技巧

跑不通的时候**逐层定位**，不要一次性看大日志：

1. **先 `/v1/models`**：能列出来就说明 key + endpoint 配对正确。
2. **再发一个不带 tools 的普通 chat**：能拿到 `content` 就说明 messages 格式没问题。
3. **再加上 `$web_search` tool，但 user 问一句不需要联网的话**（比如"你好"）：应该正常返回 `content`，不触发 `tool_calls`。
4. **最后问一个明显需要联网的问题**（比如"今天 X 城市天气"）：观察首次响应是不是 `finish_reason: "tool_calls"`。
5. 把第一次响应的 `tool_calls[0].function.arguments` 打印出来 —— 你应该看到 `search_result.search_id`，这就证明服务端真的搜了。
6. 检查你拼回去的 `messages`：

   ```
   [system, user, assistant(tool_calls=[...]), tool(tool_call_id=同一个), ...]
   ```

   顺序必须是这样，每个 assistant 的 `tool_calls` 都要有对应的 `tool` 消息跟在后面。

**最容易被忽略的两条调试日志：**

- HTTP 4xx 时，**打 response body**，不要只看 status_code。Moonshot 的 `error.message` 会直接告诉你错在哪（比如 `Invalid Authentication` / `Not found the model` / `tool_call_id is required`）。
- 把每一次发出去的 `messages` 序列化打印一遍，**对照 §5 的"常见错误对照表"** 自查。

---

## 9. TL;DR Checklist（请逐条勾选）

- [ ] Key 和 base URL 来自同一站（`.cn`↔`.cn`，`.ai`↔`.ai`）。
- [ ] Model 名字来自 `/v1/models` 的返回列表（推荐 `moonshot-v1-auto`）。
- [ ] `tools` 写法 = `[{"type": "builtin_function", "function": {"name": "$web_search"}}]`，**不**带 `parameters`。
- [ ] 有一个 `while finish_reason in (None, "tool_calls"):` 循环，且有 `max_iterations` 兜底。
- [ ] 每次收到 `tool_calls`，**先** 把 assistant 那条消息 append 回 `messages`，**再** 为每个 tool_call append 一条 `role: "tool"` 消息。
- [ ] `role: "tool"` 消息里必须有 `tool_call_id`、`name`，且 `content = json.dumps(arguments)`（**原样回显**，不要去抓网页）。
- [ ] 不假设 `arguments` 里有 `query` 字段；它可能只有 `search_result` + `usage`。

做到这 7 条，`$web_search` 就一定能跑通。

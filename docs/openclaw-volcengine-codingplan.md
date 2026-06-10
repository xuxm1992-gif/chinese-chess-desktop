# OpenClaw 接入火山方舟 Coding Plan（Lite / Pro）配置指南

> 适用对象：已经在火山引擎订阅了「方舟 Coding Plan Lite / Pro」，并希望让 **OpenClaw**（自托管个人 AI 助手）调用 Coding Plan 模型额度的用户。
>
> 适用版本：OpenClaw 2026.1.30 及以上。

---

## 0. 安全提示（务必先读）

- **API Key 一旦在聊天、截图、Git 仓库等公开渠道出现过，就必须立刻在火山方舟控制台「API Key 管理」页面 **`删除 / 重建`**，重新生成的 Key 才安全。**
- 本文中所有出现 Key 的位置一律写成占位符 `<YOUR_VOLCENGINE_API_KEY>`，你在本地手动替换即可，**不要把真实 Key 提交到任何代码仓库**。
- Coding Plan 的额度只能在「编程工具」中通过指定的 Base URL 消耗。若使用非指定 Base URL（例如通用方舟 `/api/v3`），不仅不会扣 Coding Plan 套餐额度，还会按照标准 API 价格另外计费。

---

## 1. 前提条件

1. 已订阅 **方舟 Coding Plan Lite 或 Pro**（活动页：火山引擎方舟 Coding Plan）。
2. 已在火山方舟控制台 → **API Key 管理** 页面创建并保存好一个 API Key（形如 `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx`）。
3. 已在本机或服务器上安装好 OpenClaw（`openclaw --version` 能正常输出）。

---

## 2. 关键参数速查表

OpenClaw 对火山方舟 Coding Plan 的对接，本质上只需要 **三个值**：

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| Base URL（Anthropic 协议） | `https://ark.cn-beijing.volces.com/api/coding` | OpenClaw 走 `anthropic-messages` 时用这一条，**末尾不要加 `/v3`** |
| Base URL（OpenAI 协议） | `https://ark.cn-beijing.volces.com/api/coding/v3` | OpenClaw 走 `openai-completions` 时才用这一条 |
| API Key | `<YOUR_VOLCENGINE_API_KEY>` | 火山方舟控制台创建的 Coding Plan 可用的 Key |
| Model | `ark-code-latest` | 推荐值，由方舟控制台统一调度具体模型（Doubao-Seed-Code / Kimi-K2.5 / GLM-4.7 / DeepSeek-V3.2 …）。也可写死，例如 `kimi-k2.5`、`doubao-seed-code-preview-latest` |

> ⚠️ Coding Plan 套餐额度 **仅在编程工具中生效，不能用于普通 API 调用**，违规使用可能导致订阅被停用。

---

## 3. 推荐方式：使用 OpenClaw 内置的 `volcengine-plan` Provider（最省事）

OpenClaw **官方内置** 了火山引擎的 provider，无需手写 Base URL，只要给它一个 API Key 就能跑。

### 3.1 通过交互式 onboarding 一步到位

在终端执行：

```bash
openclaw onboard --auth-choice volcengine-api-key
```

按提示粘贴你的火山方舟 API Key 即可。完成后 OpenClaw 会自动：

- 注册 `volcengine`（通用端点 `ark.cn-beijing.volces.com/api/v3`）
- 注册 `volcengine-plan`（**Coding Plan 编码端点** `ark.cn-beijing.volces.com/api/coding/v3`）
- 把默认模型设为 `volcengine-plan/ark-code-latest`

### 3.2 等价的手动配置

如果你不想跑交互式向导，可以直接编辑 `~/.openclaw/openclaw.json`：

```json5
{
  env: {
    VOLCANO_ENGINE_API_KEY: "<YOUR_VOLCENGINE_API_KEY>"
  },
  agents: {
    defaults: {
      model: {
        primary: "volcengine-plan/ark-code-latest"
      }
    }
  }
}
```

> 也可以把 `VOLCANO_ENGINE_API_KEY` 写到 `~/.openclaw/.env` 里（推荐方式），这样以 `launchd / systemd` 启动的后台 Gateway 也能读到：
>
> ```bash
> # ~/.openclaw/.env
> VOLCANO_ENGINE_API_KEY=<YOUR_VOLCENGINE_API_KEY>
> ```

完成后重启 OpenClaw Gateway：

```bash
openclaw gateway restart   # 没有该命令的话，重新打开终端 / 重启服务即可
```

---

## 4. 备选方式：自定义 Anthropic 端点（Provider 名字自取）

如果你的 OpenClaw 版本里没有 `volcengine-plan` 这个内置 provider，或者你希望显式控制 Base URL，就走这条路。

### 4.1 编辑 `~/.openclaw/agents/main/agent/models.json`

在 `providers` 里新增一个自定义 provider（名字自取，这里叫 `volcengine-ark`）：

```json
{
  "providers": {
    "volcengine-ark": {
      "baseUrl": "https://ark.cn-beijing.volces.com/api/coding",
      "api": "anthropic-messages",
      "apiKey": "<YOUR_VOLCENGINE_API_KEY>"
    }
  }
}
```

要点：

- `baseUrl` **必须**是 `https://ark.cn-beijing.volces.com/api/coding`（Anthropic 协议；OpenAI 协议要带 `/v3`）。
- `api` 固定为 `"anthropic-messages"`。
- `apiKey` 写你的火山方舟 API Key。

### 4.2 在 `~/.openclaw/agents/main/agent/auth-profiles.json` 中登记凭证（如果你的版本需要）

```json
{
  "version": 1,
  "profiles": {
    "volcengine-ark:default": {
      "type": "api_key",
      "provider": "volcengine-ark",
      "key": "<YOUR_VOLCENGINE_API_KEY>"
    }
  }
}
```

### 4.3 把默认模型指向新 provider — `~/.openclaw/openclaw.json`

```json5
{
  agents: {
    defaults: {
      model: {
        primary: "volcengine-ark/ark-code-latest"
      }
    }
  }
}
```

### 4.4 重启 Gateway

```bash
openclaw gateway restart
```

---

## 5. 备选方式：用环境变量「劫持」Anthropic 默认端点

适合所有走 `ANTHROPIC_*` 标准变量的客户端（Claude Code、OpenClaw、Cline 等都兼容）。

把以下内容追加到 `~/.bashrc`（或 `~/.zshrc`）末尾：

```bash
# 火山方舟 Coding Plan —— Anthropic 兼容协议
# 注意：URL 末尾不要写 /v3，那是 OpenAI 协议
export ANTHROPIC_BASE_URL="https://ark.cn-beijing.volces.com/api/coding"
export ANTHROPIC_AUTH_TOKEN="<YOUR_VOLCENGINE_API_KEY>"
export ANTHROPIC_MODEL="ark-code-latest"

# 避免与本地原生 Anthropic Key 冲突
export ANTHROPIC_API_KEY=""
```

让配置生效：

```bash
source ~/.bashrc      # zsh 用户：source ~/.zshrc
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_MODEL
```

对 OpenClaw 来说也可以放进 `~/.openclaw/.env`，对应字段名一样。

---

## 6. 模型选择建议

| Model Name | 说明 | 适用场景 |
| --- | --- | --- |
| `ark-code-latest` | 推荐。由方舟控制台「开通管理」页面统一调度，切换模型 3~5 分钟生效，本地无需改配置 | 想跟着官方滚动到最新最快模型 |
| `doubao-seed-code-preview-latest` | 字节自研 Doubao-Seed-Code 编码模型预览版 | 字节系深度优化的代码模型 |
| `kimi-k2.5` | Moonshot Kimi K2.5 | 长上下文 + 代码 |
| `glm-4.7` | 智谱 GLM-4.7 | 通用代码能力 |
| `deepseek-v3.2` | DeepSeek V3.2 | DeepSeek 系最新 |

> 切换模型有两种方式：① 直接在配置里改 `model.primary` 的尾段；② 保持 `ark-code-latest`，在方舟控制台「开通管理」页切换，等 3-5 分钟即可生效。

---

## 7. 验证是否对接成功

1. 启动 OpenClaw 并随便发一个简短任务（例如「写一个 Python Hello World」），看模型是否能正常应答。
2. 登录火山方舟控制台 → **Coding Plan / 开通管理**，查看「已用请求数」是否随调用上升。
   - 如果调用成功但额度没变，几乎一定是 Base URL 写错了（写成了 `/api/v3` 或 `/v1`），请回到第 2 节核对。
3. Lite 套餐每月最高约 1.8 万次请求，Pro 是 Lite 的 5 倍。单次复杂任务可能触发多次调用，属于正常现象。

---

## 8. 常见问题排查

| 现象 | 可能原因 | 解决方法 |
| --- | --- | --- |
| `No API key found` / 401 | 没设 API Key，或环境变量没生效 | `source ~/.bashrc` 或新开终端；检查 `~/.openclaw/.env` |
| 404 / `model not found` | Base URL 多了 `/v3` 或写成了通用端点 | Anthropic 协议用 `…/api/coding`，OpenAI 协议才用 `…/api/coding/v3` |
| 调用成功但 Coding Plan 额度不扣 | Base URL 不是 Coding Plan 专用端点 | 改成 `https://ark.cn-beijing.volces.com/api/coding[/v3]` |
| 提示 `provider volcengine-plan not found` | OpenClaw 版本太旧 | 升级到 ≥ 2026.1.30，或走第 4 节的「自定义 Anthropic 端点」方式 |
| 后台 Gateway（launchd / systemd）读不到 Key | 守护进程没有 shell 环境 | 把 `VOLCANO_ENGINE_API_KEY` / `ANTHROPIC_AUTH_TOKEN` 写进 `~/.openclaw/.env` |
| 切换模型后没生效 | 控制台调度需要 3-5 分钟 | 等几分钟再试；或直接在配置里写死具体 model name |

---

## 9. 最小可用片段（直接抄）

把下面这一段 **作为最终落地配置**，替换占位符即可：

`~/.openclaw/.env`：

```bash
VOLCANO_ENGINE_API_KEY=<YOUR_VOLCENGINE_API_KEY>
```

`~/.openclaw/openclaw.json`：

```json5
{
  agents: {
    defaults: {
      model: {
        primary: "volcengine-plan/ark-code-latest"
      }
    }
  }
}
```

然后重启 Gateway，进项目目录开跑即可。

---

## 10. 参考资料

- 火山方舟 Coding Plan 安装教程：<https://www.volcengine.com/article/37921>
- 火山方舟 Coding Plan API 调用指南：<https://www.volcengine.com/article/38135>
- 火山方舟 × OpenClaw 对接指南：<https://www.volcengine.com/article/38129>
- OpenClaw 中文文档 - Volcengine 提供方：<https://openclaw.zhcndoc.com/providers/volcengine>
- OpenClaw 自定义 Anthropic 端点教程：<https://wukun.work/openclaw-zi-ding-yi-anthropic-duan-dian-pei-zhi-jiao-cheng/>

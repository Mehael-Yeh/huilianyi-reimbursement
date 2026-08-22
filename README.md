# 汇联易报销 Skill + Huilianyi MCP

本仓库同时提供两层独立能力：

- **Skill = workflow layer**：根据 PDF、OFD、ZIP、XML 票据完成识别、分类、差旅判断、用户确认、草稿报销、API 回读和 Excel 核对。
- **MCP = capability layer**：向 Claude、Codex、Cursor 和其他 MCP Client 暴露可组合的汇联易原子能力。

两层共用 `src/huilianyi/` 的 Python Client、认证、凭据、异常与响应解析。MCP 不负责复杂报销决策，也没有任意 URL/method/body 执行器。

## 快速安装：复制给你的 Agent

复制下面整段内容，直接发送给你正在使用的 Agent：

```text
请把 https://github.com/Mehael-Yeh/huilianyi-reimbursement 安装或更新为可调用的 Skill，名称为 huilianyi-reimbursement。

优先使用你自带的 Skill 安装机制；如果没有，请把仓库克隆到你的用户级 Skill 目录，并安装 requirements.txt 中的 Python 依赖。仓库是私有仓库时，使用当前已有的 GitHub 授权，不要要求我把访问令牌写进聊天或命令。

安装后请完整读取 SKILL.md，运行可用的 Skill 结构校验和项目测试，并确认该 Skill 能被发现。只向我报告安装路径、当前提交或版本、校验结果；本次不要登录汇联易，也不要创建任何申请单或报销单。
```

## 安装

克隆仓库并安装 Python 依赖：

```bash
git clone https://github.com/Mehael-Yeh/huilianyi-reimbursement.git
python -m pip install -e huilianyi-reimbursement
```

将整个 `huilianyi-reimbursement` 目录添加到所用 Agent 的 Skill 搜索路径；具体导入方式和目录位置以该 Agent 的文档为准。私有仓库需要先使用有权访问该仓库的 GitHub 账号完成认证。

## Skill Mode

向 Agent 上传票据，然后说明要创建差旅申请、差旅报销或个人报销。Agent 会读取本 Skill，补充询问缺少的信息，并在写入汇联易草稿前确认。

首次使用会同时询问汇联易账号和密码：账号保存在本地配置中，密码保存在操作系统凭据库中。材料分类完成后，Agent 会主动询问本次报销的开始和结束日期。正常提报按费用类别批量处理，一类票据形成一条含多张票据的费用行；最后必须回读核验并生成 Excel 报销清单。

支持 PDF、OFD、ZIP、XML；图片票据不会上传。ZIP 加密时，Agent 会向用户索取密码，密码不会写入仓库。

本 Skill 全程使用汇联易 API，不操作浏览器；只创建或编辑草稿，不提交、删除、关闭或撤回单据。Agent 的完整工作流见 [SKILL.md](SKILL.md)。

## MCP Mode

### 初始化凭据

MCP 与 Skill 默认共用 OS keyring。首次使用运行：

```bash
python scripts/hly.py credentials-init
```

账号只保存到用户本地配置，密码只保存到操作系统凭据库。不要把密码、Cookie、Token 或 Authorization Header 写入 MCP 配置。无人值守环境也支持进程级 `HUILIANYI_USERNAME` / `HUILIANYI_PASSWORD`，但本机使用优先选择 keyring。

### 启动

```bash
python -m huilianyi_mcp.server
```

Server 使用标准 stdio MCP，不监听端口。主要 READ Tools：

- `get_current_user`、`get_company_info`、`search_users`
- `list_available_forms`、`list_expense_types`、`list_cost_centers`
- `list_travel_applications`、`get_travel_application`、`list_travel_itineraries`
- `list_reimbursements`、`get_reimbursement`、`list_invoice_items`、`get_invoice`
- `get_loan_balance_summary`、`get_approval_history`

受限 DRAFT_WRITE Tools：

- `create_travel_draft`
- `create_reimbursement_draft`
- `upload_attachment`
- `attach_invoice`

所有返回值使用稳定的 `{ok, data}` 或 `{ok: false, error}` JSON envelope；分页结果附带 `pagination`。账号、公司和错误响应经过字段白名单或敏感字段清洗。

### Codex

Codex 桌面端可在 **Settings → MCP servers → Add server** 中添加 stdio Server，或写入 `~/.codex/config.toml`：

```toml
[mcp_servers.huilianyi]
command = "python"
args = ["-m", "huilianyi_mcp.server"]
cwd = "/absolute/path/to/huilianyi-reimbursement"
startup_timeout_sec = 20
tool_timeout_sec = 120
default_tools_approval_mode = "writes"
```

配置后重启客户端，并用 `/mcp` 检查连接。参见 [OpenAI 官方 MCP 文档](https://learn.chatgpt.com/docs/extend/mcp)。

### Claude / Cursor / 其他 MCP Client

把同一个 stdio 命令写入客户端的 MCP 配置；常见 JSON 形式如下，具体文件位置以客户端当前文档为准：

```json
{
  "mcpServers": {
    "huilianyi": {
      "command": "python",
      "args": ["-m", "huilianyi_mcp.server"],
      "cwd": "/absolute/path/to/huilianyi-reimbursement"
    }
  }
}
```

### MCP 安全边界

默认仅开放 `READ` 和经过草稿状态校验的 `DRAFT_WRITE`。Server 不包含提交、审批、驳回、删除、撤回、关闭或付款 Tool。即使前端研究发现这些接口，也只会进入 [API Registry](data/api_registry.yaml)，并保持 `mcp_exposed: false`。

## API 研究

- [当前 API inventory](docs/api-inventory.md)
- [完整能力地图与验证状态](docs/huilianyi-api-map.md)
- [可追溯研究记录](docs/api-research/)
- [机器可读 Registry](data/api_registry.yaml)

只读研究助手 `scripts/research_api_map.py` 会记录响应结构和生产前端字面路径，不保存账号值、OID、Token、Cookie 或签名 URL，也不会调用从 Bundle 中新发现的路径。

## 测试

```bash
python -m unittest discover -s tests -v
```

真实账号集成测试默认关闭，只允许显式启用 READ：

```bash
HUILIANYI_INTEGRATION_READONLY=1 python -m unittest tests.test_integration_readonly -v
```

写入集成测试不在默认测试集中；任何未来写测试都必须限制到 status 1001 草稿并单独标记。

## 许可证

[MIT License](LICENSE)

# 安装与首次运行

## 环境

- Python 3.10+
- 可访问汇联易 A2 服务的网络
- 用于 Excel 核对表的 Node.js 与 `@oai/artifact-tool`（Codex 工作区已提供）

```bash
python -m pip install -r requirements.txt
python scripts/hly.py --help
```

## 凭据

账号通过 `--username` 传入。密码通过交互提示或当前进程的 `HLY_PASSWORD` 读取，不应写入命令历史、配置文件或仓库。

## 首次校准

```bash
python scripts/hly.py profile --username <账号> --output tmp/profile.json
python scripts/hly.py history --username <账号> --output tmp/history.json
```

向用户确认画像中的公司、部门、代理人、参与人、项目和事由。历史 OID 不是永久配置，正式写入前必须重新解析。

## 票据预检

```bash
python scripts/invoice_extract.py <文件...> --output tmp/invoice-review.json
```

逐项确认低置信度、重复、金额冲突和“待确认”记录后，再创建申请或报销草稿。

# 安装与首次运行

## 环境

- Python 3.10+
- 可访问汇联易 A2 服务的网络

克隆仓库，将整个目录添加到所用 Agent 的 Skill 搜索路径；具体导入方式以该 Agent 的文档为准。

```bash
git clone https://github.com/Mehael-Yeh/huilianyi-reimbursement.git
cd huilianyi-reimbursement
python -m pip install -r requirements.txt
python scripts/hly.py --help
```

## 凭据

首次运行：

```bash
python scripts/hly.py credentials-init
```

命令会同时询问账号和密码并先验证登录。账号保存在本地 Codex 配置目录，密码保存在操作系统凭据库；两者都不进入仓库、命令历史或状态 JSON。后续命令可以省略 `--username`。

## 首次校准

```bash
python scripts/hly.py profile --output tmp/profile.json
python scripts/hly.py history --output tmp/history.json
```

向用户确认画像中的公司、部门、代理人、参与人、项目和事由。历史 OID 不是永久配置，正式写入前必须重新解析。

## 票据预检

```bash
python scripts/invoice_extract.py <文件...> --output tmp/invoice-review.json
```

若 ZIP 加密，脚本会交互提示密码。Agent 应先向用户索取密码，不猜测、不记录，也不把密码写入仓库。

逐项确认低置信度、重复、金额冲突和“待确认”记录后，再创建申请或报销草稿。

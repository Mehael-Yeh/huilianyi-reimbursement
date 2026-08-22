# 汇联易报销填报

面向 Agent 的汇联易 A2 API 草稿填报工具。项目覆盖历史校准、票据识别与分类、差旅申请、差旅报销、个人报销、费用保存、回读验收和 Excel 核对表交付。

## 功能

- 从历史申请和报销中校准公司、部门、代理人、参与人及常用费用类型。
- 从 PDF、OFD、ZIP、XML 提取文本、发票号码和含税金额。
- 使用项目名称、服务名称、销售方和文件名进行可解释分类。
- 支持通行费、酒店、停车、打车、其他交通、餐饮、礼品、加油和油卡等规则。
- 创建差旅申请、关联差旅报销和独立个人报销草稿。
- 支持多张同类发票关联同一申请预算池，以及无申请类别的真实费用增补。
- 支持无票出差补贴和通行汇总单附件。
- 生成包含分类、金额、差额和保存状态的 Excel 核对表。

## 安装

需要 Python 3.10 或更高版本：

```bash
python -m pip install -r requirements.txt
```

密码默认通过安全交互提示输入，也可以在当前进程环境中设置 `HLY_PASSWORD`。不要把 `.env` 或凭据文件提交到仓库。

## 快速开始

查看命令：

```bash
python scripts/hly.py --help
```

预检票据：

```bash
python scripts/invoice_extract.py <票据文件...> --output tmp/invoice-review.json
```

读取历史并建立画像：

```bash
python scripts/hly.py profile --username <账号> --output tmp/profile.json
python scripts/hly.py history --username <账号> --output tmp/history.json
```

所有外部写入命令都需要显式传入 `--confirm-draft-write`。完整的申请、报销、发票和无票费用命令见 [SKILL.md](SKILL.md) 与 [CLI Reference](docs/wiki/CLI-Reference.md)。

## Excel 核对表

费用保存并回读后，先合并分类结果与汇联易费用：

```bash
python scripts/hly.py prepare-review --username <账号> \
  --report <报销单号> --invoice-review tmp/invoice-review.json \
  --output tmp/reimbursement-review.json
```

再生成工作簿：

```bash
node scripts/build_review_workbook.mjs \
  tmp/reimbursement-review.json outputs/报销分类金额核对.xlsx
```

工作簿包含“汇总、票据明细、类别核对”三张表，并保留自动建议、用户确认、金额来源和保存状态。

## 项目结构

```text
SKILL.md                         Agent 工作流入口
scripts/hly.py                   汇联易命令行入口
scripts/hly_api.py               鉴权与 HTTP 客户端
scripts/hly_workflow.py          草稿、费用与验收逻辑
scripts/invoice_extract.py       多格式票据提取与分类
scripts/review_export.py         分类与汇联易回读合并
scripts/build_review_workbook.mjs Excel 核对表生成器
references/                      API、字段、分类和关系模型
tests/                           自动化测试
docs/wiki/                       GitHub Wiki 源文件
```

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile scripts/*.py
```

## 文档

- [Wiki 文档首页](docs/wiki/Home.md)
- [票据分类与金额提取](references/invoice-classification.md)
- [申请与报销关系](references/workflow-model.md)
- [费用保存](references/invoice-landing.md)
- [Excel 核对表](references/review-workbook.md)

## 许可证

[MIT License](LICENSE)

---
name: huilianyi-reimbursement
description: 使用汇联易 A2 API 校准历史习惯、识别和分类票据、创建差旅申请/差旅报销/个人报销草稿、保存费用并生成核对表。仅处理草稿，永不提交、删除、关闭或撤回单据。
license: MIT
metadata:
  version: 4.3.0
  author: Mehael Yeh
  platforms: [linux, windows, darwin]
---

# 汇联易报销填报

只使用汇联易 A2 API 完成历史校准、票据识别、草稿创建、费用保存、回读验收和 Excel 核对表交付。不得手动操作或自动化操作浏览器；若 API 缺少能力，停止写入并向用户说明具体缺口。

## 安全边界

- 仅创建或编辑 `status=1001` 的草稿。
- 不调用提交、删除、关闭、撤回端点；不自动清理已有单据或费用。
- 差旅报销只关联 `status=1003` 且 `closed=false` 的差旅申请。
- 个人报销不关联申请单。
- 初次使用必须同时询问账号和密码，先验证登录，再把账号写入本地配置、密码写入操作系统凭据库。不得把密码写入普通文件、命令历史、日志或输出。
- OID、表单和费用类型必须从当前租户动态查询，不能固化历史值。
- 外部写入前需获得用户明确授权；一次授权不包含提交或清理权限。

## 环境与入口

```bash
python -m pip install -r requirements.txt
python scripts/hly.py --help
```

统一使用 `scripts/hly.py` 操作汇联易；票据预检使用 `scripts/invoice_extract.py`。支持上传 PDF、OFD、ZIP、XML，不上传图片格式票据。

首次使用先初始化本地凭据；后续命令可省略 `--username`：

```bash
python scripts/hly.py credentials-init
```

## 工作流

### 1. 校准历史

首次使用先生成习惯画像，后续至少读取近期同类单据：

```bash
python scripts/hly.py profile --username <账号> --output tmp/profile.json
python scripts/hly.py history --username <账号> --output tmp/history.json
```

向用户确认费用承担公司、部门、代理人、参与人、项目和事由。画像中的 OID 只作缓存，每次写入前重新解析。

### 2. 识别并分类全部材料

```bash
python scripts/invoice_extract.py <文件...> --output tmp/invoice-review.json
```

ZIP 若加密，先向用户索取密码；不得猜测、记录或写入仓库。交互运行时脚本会安全提示输入，也可仅在当前进程通过 `INVOICE_ZIP_PASSWORD` 提供。一个压缩包内同一发票的 PDF、OFD、XML 版本按发票号码合并，不能重复计金额。

需要把 ZIP 内票据保存到汇联易时，使用 `--extract-dir <临时目录>` 解密并仅提取去重后选中的文件；可用 `--prefer-format OFD|XML|PDF` 指定同一发票优先使用的格式。后续 `add-invoice` 使用结果中的 `extractedFile`，不得直接上传仍处于加密状态的 ZIP。

读取 [票据分类与金额提取](references/invoice-classification.md)：

- 先区分发票与行程单、汇总单等附件；附件不重复计金额。
- 金额优先使用明确的含税合计字段，不能简单取全文最大数字。
- 同一发票号码或内容哈希只计一次。
- 分类冲突、金额冲突、文本缺失或低置信度条目必须交由用户确认。
- 未命中规则时标记“待确认”，不得默认归入任一费用类型。

分类后汇总为 `travel` 与 `personal` 两组。差旅申请预算按当前已知差旅类别汇总；预算类目是汇总池，不要求与每张发票一一对应。

材料识别和分类完成后，必须主动询问用户本次报销的开始日期与结束日期。不得从文件夹名称、发票日期或拟关联的历史申请单中擅自推断。确认后的日期同时用于新建差旅申请和本次报销核对。

### 3. 创建草稿

差旅申请以同类历史申请为模板，预算必须来自已确认的差旅分类汇总：

```bash
python scripts/hly.py create-application \
  --username <账号> --template-application <模板申请单号> \
  --agent <代理人> --participant <参与人> \
  --start <YYYY-MM-DD> --end <YYYY-MM-DD> \
  --travel-plan <费用计划.json> --confirm-draft-write
```

申请审批通过后创建关联差旅报销；个人报销可独立创建：

```bash
python scripts/hly.py create-reports \
  --username <账号> --target-application <已审核申请单号> \
  --create-personal-report --confirm-draft-write
```

关联字段和日期语义见 [申请与报销关系](references/workflow-model.md) 与 [表单字段](references/form-fields.md)。

保存草稿后必须回读差旅申请，确认顶层总额、`budgetDetailDTO.amount` 和各类别预算金额均与分类汇总一致；任一处为零或不一致都不算完成。

### 4. 保存费用

有票费用必须按“归属单据 + 费用类别”分组，一组创建一条费用行。每组 JSON 是非空的 `{path, amount}` 数组：

```bash
python scripts/hly.py add-invoice-batch \
  --report <报销单号> --invoice-batch <本类别.json> \
  --expense-type <费用类型> --confirm-draft-write
```

原始文件上传接口一次仍只接收一个文件，所以同一类别内并发上传原文件；随后整组只调用一次 OCR、一次批量查验和一次 V5 费用创建，并把所有有效票据放进同一条费用行。不要把发票打 ZIP 后当成一张票上传。已审批历史中同一费用行可包含数十张票据；只有 API 明确返回数量上限时才按稳定顺序分块。

`add-invoice` 仅用于单票诊断或重试，不得作为正常批量提报的循环入口：

```bash
python scripts/hly.py add-invoice \
  --username <账号> --report <报销单号> --file <票据文件> \
  --expense-type <费用类型> [--amount <金额>] --confirm-draft-write
```

- 同类全部发票复用申请中的同类预算行 ID 列表。
- 本地文本层没有金额时使用汇联易 OCR/查验的含税金额；显式金额与查验金额不一致时停止。
- 申请没有的实际类别使用空预算列表保存，不得错分；停车费等新增类别允许形成差额。
- 酒店入住城市从销售方名称或地址推断，多地用中文逗号连接；日期使用整张差旅报销范围。
- 过路费材料含通行单或汇总单时，通过 `--attachment` 附在对应费用上，不作为发票重复计金额。

无票费用：

```bash
python scripts/hly.py add-manual-expense \
  --username <账号> --report <报销单号> \
  --expense-type 出差补贴 --amount <金额> --date <YYYY-MM-DD> \
  --field 补贴天数=<整数> --field 客户名称= --confirm-draft-write
```

出差补贴默认按“金额 = 补贴天数 × 100”计算，客户名称允许为空。该公式是跨公司通用默认值，不是强制审查标准；历史单据、公司制度或用户确认的标准不同时，以实际标准为准并在核对结果中提示差异。无票费用必须补齐默认分摊接口省略的金额、币种、费用类型、人员和单据公司字段。

详细 API 顺序及状态见 [费用保存](references/invoice-landing.md)。

### 5. 回读验收

```bash
python scripts/hly.py verify-report --username <账号> --report <报销单号>
python scripts/hly.py audit-travel-pair --username <账号> \
  --application <申请单号> --report <报销单号>
```

必须确认：

- 费用没有 `INVOICE_ASYNC_ERROR`；无票异步状态 `100=失败`、`101=处理中`、`102=成功`。
- 每张发票已绑定正确费用类型，附件不计金额。
- 报销单总额等于费用分组金额之和。
- 差旅申请与报销按类别列出预算、实际和差额，不以差额阻止真实费用保存。

### 6. 交付 Excel 核对表

费用保存和回读结束后，必须向用户交付 `.xlsx` 核对表，至少包含文件名、格式、发票号码、建议分类、归属单据、识别金额、金额来源、分类依据、置信度、核对状态、汇联易费用编号和保存状态。生成与验收要求见 [Excel 核对表](references/review-workbook.md)。

最后一步必须运行一体化导出命令；未生成并校验 `.xlsx` 时，任务不得报告完成：

```bash
python scripts/hly.py finalize-review \
  --report <差旅报销单号> --report <个人报销单号> \
  --invoice-review tmp/invoice-review.json \
  --review-output tmp/reimbursement-review.json \
  --xlsx-output outputs/报销分类金额核对.xlsx
```

交付前应报告差旅申请单、关联申请单、两张报销单的单号和金额，以及 Excel 的绝对路径；不得回显账号或密码。

## 参考

- [票据分类与金额提取](references/invoice-classification.md)
- [申请与报销关系](references/workflow-model.md)
- [费用保存](references/invoice-landing.md)
- [表单字段](references/form-fields.md)
- [费用类型](references/expense-types.md)
- [API 端点](references/api-endpoints.md)
- [鉴权](references/api-notes.md)
- [Excel 核对表](references/review-workbook.md)

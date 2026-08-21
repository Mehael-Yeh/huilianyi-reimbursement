---
name: huilianyi-reimbursement
description: "触发: 报销/差旅/汇联易/填报销单。读取历史校准→发票分类→创建差旅申请、差旅报销、个人报销草稿→API上传识别并落账；永不提交或删除。"
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, windows, darwin]
metadata:
  hermes:
    tags: [汇联易, 报销, 差旅, 发票, huilianyi, helios]
    related_skills: [hermes-gateway-service]
---

# 汇联易报销填报 skill

使用汇联易 A2 API 完成“历史校准→发票分类→三类单据草稿→发票费用行→回读验收”。浏览器只用于 API 无法覆盖的人工复核，不作为主链。

## 铁律

- 绝不调用提交、删除、关闭、撤回接口。
- 只创建或编辑 `status=1001`（编辑中）的草稿。
- 已有单据一律保留；测试草稿也不自动清理。
- 差旅报销只能关联 `status=1003` 且 `closed=false` 的差旅申请。
- 费用字段、预算、公司归属或类别不确定时先问用户，不猜。
- 密码只从交互输入或 `HLY_PASSWORD` 环境变量读取，绝不写入仓库、日志、状态文件或输出。
- 发票只允许加入编辑中草稿；已审核/已付单据不得修改。

## 环境

```bash
python -m pip install -r requirements.txt
```

API 入口：

- OAuth：`https://console-a2.huilianyi.com/proxy/oauth/token/v2`
- 业务 API：OAuth 返回的 `realm_base_service_url`
- 收据/发票网关：`https://console-a2.huilianyi.com`

统一命令入口：`python scripts/hly.py ...`。不要再运行旧抓包脚本或硬编码 OID 的实验脚本。

## Step 1：每次先读历史校准

至少读取最近 3 张申请单、3 张报销单及其发票分组；新账号或历史模式不一致时读取全部可见记录：

```bash
python scripts/hly.py history --username <账号> --output tmp/hly-history.json
```

必须核对：

1. 近期费用承担公司、部门、代理人、参与人、项目、事由。
2. 差旅申请状态、是否关闭、日期、预算金额。
3. 差旅报销与申请的 OID/单号/日期映射。
4. 个人报销是否完全无申请关联。
5. 发票分组总额是否等于报销单 `totalAmount`。

### 已验证的关系模型

- 差旅报销关联申请必须同时写三处：
  1. 顶层 `applicationOID`、`applicationBusinessCode`、`applicationFormOID`；
  2. 唯一一条 `expenseReportApplicationDTOS`；
  3. `applicationStartAndEndDateMap` 的 `<OID>+start_date/end_date`。
- `custFormValues` 中“关联申请”可以仍为 `null`；真正关系以上述三处为准。
- 个人报销必须满足：顶层申请字段为 `null`、DTO 数组为空、日期映射为空。
- 已付差旅报销可能使申请自动 `closed=true`；禁止把已关闭申请用于新报销。
- 申请预算是上限/计划，不要求等于最终报销金额。
- 报销公司可能与申请公司不同。优先按发票抬头和近期同类报销判断，不得直接复制申请公司。
- 申请日期使用中国时区转 UTC；报销关联日期使用汇联易的“本地墙上时间+Z”格式。使用脚本转换，不手拼。

详细说明见 `references/workflow-model.md`。

## Step 2：发票识别与分类

规则见 `references/invoice-classification.md`。核心：

- 差旅：过路费、酒店、停车费、打车费、其他交通。
- 个人：餐费、礼品费、里程补贴。
- 餐饮金额 `>80` 元归礼品/招待；`80` 元整仍归餐费。
- 通行费汇总单、行程单仅作附件，不重复计金额。
- 同发票号码只计一次。
- 先核对发票抬头，再决定费用承担公司。

输出清单必须包含：文件、发票号、日期、含税金额、类别、目标单据、是否计入合计、待核对原因。

## Step 3：创建草稿

### 差旅申请单

必须有：费用公司/部门、代理人、参与人、起止日期、交通工具、事由、是否总务订机票。

当前脚本创建“表头完整、预算为 0”的草稿。若公司要求资金明细/预算行，必须向用户确认费用类型和金额；在预算行 API 尚未实测前，不得伪造预算结构。

### 差旅报销单

- 目标申请必须已审核且未关闭。
- 日期和参与人来自目标申请。
- 公司/部门来自票据抬头与历史校准。
- 新草稿初始金额为 0，随后由 `v5/invoices` 费用行自动累计。

### 个人报销单

- 不关联任何申请。
- 事由根据票据写成可解释的业务描述，如“客户送礼，请客招待”。

创建三类草稿：

```bash
python scripts/hly.py create-drafts \
  --username <账号> \
  --target-application <已审核TZ单号> \
  --agent <代理人姓名> \
  --participant <参与人姓名> \
  --state tmp/hly-state.json \
  --confirm-draft-write
```

状态文件用于防止重跑重复建单；其中不保存 token 或密码。

## Step 4：发票纯 API 落账

对每张计入金额的发票执行：

1. `POST /api/upload/attachment`
2. `POST /receipt/api/receipt/ocr/v3`
3. `POST /receipt/api/receipt/verify/batch`
4. 动态查询 `POST /api/expense/type/byUser`
5. `POST /invoice/api/invoice/defaults`
6. `POST /api/expense/default/apportionment`
7. `POST /invoice/api/invoice/tax/amount/by/receipts`
8. `POST /invoice/api/v5/invoices`

```bash
python scripts/hly.py add-invoice \
  --username <账号> \
  --report <编辑中ER单号> \
  --file <发票PDF> \
  --expense-type <费用类型> \
  --amount <含税金额> \
  --confirm-draft-write
```

关键规则：

- `verify` 返回的 `receiptOID` 是关键；数字 `receipt.id` 可以为 `null`。
- `tax/amount` 返回的 `invoiceOID` 是临时身份。传给 `v5/invoices` 会报“该费用已被其他人删除”，最终请求必须移除它。
- 费用类型 OID 必须动态查询，不使用文档中的固定 OID。
- `v5/invoices` 成功后会直接绑定费用行并更新报销总额，不需要手拼 `expenseReportInvoices`。

完整配方见 `references/invoice-landing.md`。

## Step 5：回读验收

每次写入后必须回读：

- 申请：`GET /api/application/{oid}?showValue=true`
- 报销单：`GET /api/v3/expense/reports/{oid}`
- 发票/费用行：`GET /api/expense/report/invoices/v2?expenseReportOID={oid}`

验收条件：

- 新单据状态均为 `1001`。
- 差旅报销关联单号与用户指定申请一致，且三处关联结构完整。
- 个人报销无申请关系。
- `invoiceCount` 等于已成功落账票数。
- 发票分组 `totalInvoiceAmount` 与单据 `totalAmount` 一致（浮点展示按货币精度比较）。
- 不以 HTTP 成功代替业务验收。

## 参考

- `references/workflow-model.md`：历史关系、状态和日期模型。
- `references/invoice-landing.md`：当前唯一有效的发票落账配方。
- `references/invoice-classification.md`：分类规则。
- `references/form-fields.md`：字段语义参考；OID 必须动态获取。
- `scripts/hly_api.py`：鉴权与 HTTP 客户端。
- `scripts/hly_workflow.py`：关系建模、草稿构造、发票落账。
- `scripts/hly.py`：跨平台 CLI。

---
name: huilianyi-reimbursement
description: "触发: 报销/差旅/汇联易/填报销单。读取历史校准并先分类票据；个人报销独立建单，差旅按申请审批通过后再关联报销的顺序创建；永不提交或删除。"
license: MIT
metadata:
  version: 3.4.0
  author: Hermes Agent
  platforms: [linux, windows, darwin]
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
- 费用字段、公司归属或类别不确定时先问用户，不猜。
- 差旅申请预算按当时已知的分类汇总填写；不得再创建零预算申请，也不得为了凑申请而错分实际费用。
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

## Step 0：首次运行初始化画像（新账号/无画像时必做）

个人信息（手机号、姓名、公司、OID）**不写入 skill 本体**。首次运行登录成功后，**向用户申请读取其历史报销数据**，用它建立"报销习惯画像"，供后续填单参考与确认：

```bash
python scripts/hly.py profile --username <账号> --output tmp/hly-profile.json
```

该命令读最近申请单/报销单，聚合输出：

- **费用承担公司**（名称 + 出现次数 + 运行时 OID 缓存）
- **部门**（同上）
- **代理人**（历史中最常使用的，如"曾乐/周易嘉"）
- **常用费用类型**（及在多少张单据中出现）——用于自动判断差旅/个人分类
- **近期单据样本**（businessCode/状态/金额/分类汇总）

**用法（关键铁律）**
1. 运行后把画像展示给用户，**逐一确认或更正**：默认费用承担公司、开户公司（浙江佑谦，可能≠报销挂账公司嘉兴锐石）、代理人、参与人、常用事由。
2. **OID 只是运行时缓存，绝不定死**：每次实际填单前须按 `account` 接口与 `form-fields.md` 重新校验；Agent/参与人每次用 `find_user` 按姓名查最新 `userOID`，不直接沿用画像里的 OID。
3. 画像只存习惯与频次，**不含密码**；账号密码仅经 `--username` + `HLY_PASSWORD`/交互注入，永不落盘。
4. 没有历史记录（全新账号）时，画像为空，逐项向用户问询并当场确认。

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
- 正常流程是出差前提交并通过差旅申请，出差后关联报销。
- 当前业务允许事后补流程：先按已发生费用创建并审批差旅申请，再创建关联的差旅报销。
- 事后补流程中，申请与报销的分类、金额通常接近，但不是强制相等；停车费等意外费用可在报销中增补。
- 报销公司可能与申请公司不同。优先按发票抬头和近期同类报销判断，不得直接复制申请公司。
- 申请日期使用中国时区转 UTC；报销关联日期使用汇联易的“本地墙上时间+Z”格式。使用脚本转换，不手拼。

详细说明见 `references/workflow-model.md`。

## Step 2：先识别和分类全部票据

规则见 `references/invoice-classification.md`。核心：

**发票交付格式（可直接丢进目录/压缩包）：**
- **PDF**（.pdf）：电子发票、扫描件（主格式）
- **OFD**（.ofd）：新版数电票；可提取文本并进入汇联易 OCR，但当前租户的最终费用保存实测仍可能返回 500，不能宣称全链路成功
- **ZIP**（.zip）：电子票据打包文件
- **XML**（.xml）：电子票据结构化原件

上传白名单严格限定为 PDF/OFD/ZIP/XML。PNG/JPG/JPEG 等图片即使汇联易支持也不上传；RAR/7Z、Office 文件等也不作为本 skill 的发票或费用附件上传。

> OFD 必须完成“上传→OCR→查验→费用保存→回读”后才能标记成功。2026-08-22 的真实 OFD 测试在最终 `v5/invoices` 返回 500，未新增费用行；在修复最终保存前只标记为“识别通过、落账失败”。

- 差旅：过路费、酒店、停车费、打车费、其他交通。
- 个人：餐费、礼品费、里程补贴。
- 餐饮金额 `>40` 元归礼品/招待；`40` 元及以下仍归餐费。
- 通行费汇总单、行程单仅作附件，不重复计金额。
- 同发票号码只计一次。
- 先核对发票抬头，再决定费用承担公司。

输出清单必须包含：文件、发票号、日期、含税金额、类别、目标单据、是否计入合计、待核对原因。

必须遍历用户提供目录中的全部材料，完成去重和汇总；只挑每类一张“代表发票”不构成完成。申请类目记录的是该类预算总额，不是一条预算对应一张发票。

分类完成后先生成统一费用计划。`travel` 是差旅申请的预算基线，后续所有实际差旅票据进入差旅报销；`personal` 只进入个人报销。例如：

```json
{
  "travel": [
    {"expenseType": "过路费", "amount": 14.60},
    {"expenseType": "酒店", "amount": 220.15}
  ],
  "personal": [
    {"expenseType": "礼品费", "amount": 138.00}
  ]
}
```

## Step 3：创建草稿

### 差旅申请单

必须有：费用公司/部门、代理人、参与人、起止日期、交通工具、事由、是否总务订机票。

当前事后补流程用当时已知的 `travel` 费用计划创建资金明细，金额按类目汇总。预算行结构从历史同类申请复制并清除旧单据身份；模板缺少某个计划内费用类型时停止并换用包含该类型的历史模板，不伪造 OID。

### 差旅报销单

- 目标申请必须已审核且未关闭。
- 日期和参与人来自目标申请。
- 公司/部门来自票据抬头与历史校准。
- 新草稿初始金额为 0，随后由 `v5/invoices` 费用行自动累计。
- 同一类目的多张发票全部关联该类申请预算项目；这是多对一/多对多汇总关系，不是一一对应。
- 若实际发生的类目未出现在申请中（如额外停车费），按真实类别新增“手录费用”并附票，不能塞入其他预算类目。
- 报销金额可以低于、等于或高于申请类目金额；差额用于提示和解释，不作为阻止落账的条件。

### 个人报销单

- 不关联任何申请。
- 事由根据票据写成可解释的业务描述，如“客户送礼，请客招待”。

### 当前事后补流程的强制顺序

1. 分类全部票据，分离 `travel` 与 `personal`。
2. 创建按已知分类汇总金额的差旅申请草稿。
3. 停止，等待用户在汇联易提交并审批通过申请；skill 不代为提交或审批。
4. 回读确认申请 `status=1003` 且 `closed=false`。
5. 创建关联该申请的差旅报销草稿；个人报销可在这一阶段独立创建。
6. 将全部实际差旅票据加入差旅报销；同类票据复用对应预算行 ID，新增类别走手录费用。个人票据加入个人报销。
7. 审计票据完整性、类目覆盖和金额差异；差异不等于失败。

第一阶段只创建差旅申请：

```bash
python scripts/hly.py create-application \
  --username <账号> \
  --template-application <包含所需费用类型的历史TZ单号> \
  --agent <代理人姓名> \
  --participant <参与人姓名> \
  --start <YYYY-MM-DD> --end <YYYY-MM-DD> \
  --travel-plan tmp/expense-plan.json \
  --state tmp/hly-state.json \
  --confirm-draft-write
```

申请由用户审批通过后，第二阶段创建报销单：

```bash
python scripts/hly.py create-reports \
  --username <账号> \
  --target-application <刚审批通过的TZ单号> \
  --state tmp/hly-state.json \
  --confirm-draft-write
```

**个人报销单可独立提前生成，不依赖差旅申请审批**：它不关联任何申请单（无等待环节），只要存在`personal`票据即可直接调用。可在阶段一同时完成，也可单独在任意时点生成：

```bash
python scripts/hly.py create-reports --username <账号> \
  --create-personal-report --state tmp/hly-state.json --confirm-draft-write
```

只有存在个人报销票据时，才额外传入 `--create-personal-report`；个人报销不会关联上述差旅申请。因此个人报销是"生成即完成"，无需经历差旅那种"建申请→等审批→再关联"的两阶段。

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

酒店费用必须从酒店销售方名称/地址推断入住城市；多地用中文逗号连接，例如 `上海，昆山，无锡`。开始结束日期统一写关联差旅报销单的完整起止日期。无法可靠判断城市时停止并要求用户给出 `--hotel-city`，不得猜测。

过路费材料若包含通行费汇总单/通行单，该文件不计金额、不做第二张发票 OCR，而以 `--attachment <文件>` 上传到过路费费用行的 `attachments`。历史回读已确认该结构与网页一致。

**增量报销与去重（支持会话过期后继续追加）**：`add-invoice`/`add-manual-expense` 先按指定 ER 单号定位已有草稿（不新建），并在 OCR 拿到发票号后与单内已有发票号比对——**重复票跳过并返回 `duplicate:true` 提示，新票才落账**。因此同一 ER 单可分多次追加发票，跨会话/会话过期也安全：再次上传已存在的发票只会被提醒、不会重复绑定。用 `verify-report` 可随时查看单内全部发票号。

关键规则：

- `verify` 返回的 `receiptOID` 是关键；数字 `receipt.id` 可以为 `null`。
- `tax/amount` 返回的 `invoiceOID` 是临时身份。传给 `v5/invoices` 会报“该费用已被其他人删除”，最终请求必须移除它。
- 费用类型 OID 必须动态查询，不使用文档中的固定 OID。
- 对关联申请中同类别的全部预算行，取数值 `budgetDetail.id` 组成 `applicationCustomBudgetId` 列表；不要传 `budgetOID`，也不要传标量。
- 同类每张发票重复使用同一预算 ID 列表，并把默认分摊接口返回的 `expenseApportion` 写入最终费用行。
- 申请没有该类别时传空列表，按真实类别创建手录费用；不得报错、跳过或改成已有类别。
- `v5/invoices` 成功后会直接绑定费用行并更新报销总额，不需要手拼 `expenseReportInvoices`。

完整配方见 `references/invoice-landing.md`。

### 无票手录费用

费用类型声明 `invoiceRequired=false` 且 `pasteInvoiceNeeded=false` 时，可完全跳过上传、OCR、查验和税额接口。使用 v6 保存无票费用：

```bash
python scripts/hly.py add-manual-expense \
  --username <账号> --report <编辑中ER单号> \
  --expense-type 出差补贴 --amount <金额> --date <YYYY-MM-DD> \
  --field 补贴天数=<天数> --field 客户名称=<客户名称> \
  --confirm-draft-write
```

出差补贴固定为 100 元/天，金额必须严格等于 `补贴天数 × 100`。客户名称允许留空；请求中按网页行为编码为 `value=null`、`showValue=""`，不得伪造测试文案。

完整流程为：从无异步错误的历史同类无票费用读取完整详情 → 使用当前报销单的 `applicantJobId`，不要依赖可能已丢失岗位的历史 `FINISHED` DTO → 校验 100 元/天 → 调用默认分摊并补齐接口省略的金额、币种、费用类型、单据公司和人员字段 → 申请预算关联 → `POST /invoice/api/validate/invoice/async` → 预校验无错才调用 `POST /invoice/api/v6/invoices` → 轮询回读。请求必须为 `withReceipt=false`、空 `receiptList`，并与网页草稿语义保持 `valid=false`、`paymentCompanyOID=null`。编辑中报销单的正常费用状态可以是 `SUBMITTED` 或 `FINISHED`；`invoiceSaveStatus=101` 是异步处理中，`100` 是失败，`102` 是异步保存成功，网页同步保存也可能为 `null`。成功状态还必须无 `INVOICE_ASYNC_ERROR`。总额或行数增加不能代替终态验收。

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
- `asynchronousSaveFailures` 必须为空，且 `businessAccepted=true`；任何“费用保存失败”标签都必须判失败。
- 发票分组 `totalInvoiceAmount` 与单据 `totalAmount` 一致（浮点展示按货币精度比较）。
- 差旅申请预算与差旅报销费用按规范化后的类别汇总比较；`其他交通` 与历史中的 `市内交通费` 视为同类。
- 每类输出申请汇总额、报销汇总额、发票张数和差额。报销中没有申请类目的费用标记为 `manual-expense`，但不判失败。
- 验收重点是用户提供的全部有效发票均已处理、同类发票归入同类预算、额外费用真实增补；金额相等不是验收条件。
- 不以 HTTP 成功代替业务验收。

```bash
python scripts/hly.py audit-travel-pair \
  --username <账号> --application <TZ单号> --report <ER单号>
```

**回读验收后必须给用户一段中文简报告（不是只贴 JSON）**，包含：
- 本次共处理几张发票、分属哪些类别；
- 差旅申请预算 vs 报销费用：每类申请额/报销额/张数/差额；
- 个人报销单独说明（不关联申请，已独立生成）；
- 重复发票与待核对项列表（提示用户；
- 是否有新增/未覆盖的类别（标记 manual-expense，不判失败）；
- 明确的下一步：哪些单已建好草稿待你在网页提交审批。

报告用条目式中文，先给结论（成功/待办），再给明细，符合用户"简短口头版"偏好。

## 参考

- `references/workflow-model.md`：历史关系、状态和日期模型。
- `references/invoice-landing.md`：当前唯一有效的发票落账配方。
- `references/invoice-classification.md`：分类规则。
- `references/form-fields.md`：字段语义参考；OID 必须动态获取。
- `scripts/hly_api.py`：鉴权与 HTTP 客户端。
- `scripts/hly_workflow.py`：关系建模、草稿构造、发票落账。
- `scripts/hly.py`：跨平台 CLI。

# 申请单与报销单关系模型

本模型基于 2026-08-21 对当前账号全部可见历史的只读校准：6 张原有差旅申请、8 张原有报销单，另加本次创建的 3 张测试草稿及 4 张成功落账发票。

## 状态

| 对象 | 状态 | 含义 | 自动化动作 |
|---|---:|---|---|
| 申请单/报销单 | 1001 | 编辑中 | 允许创建、编辑、加票 |
| 差旅申请单 | 1003 | 已审核通过 | 仅当 `closed=false` 时可作为新差旅报销的关联源 |
| 报销单 | 1005 | 已付 | 只读，不修改 |
| 申请单 | 1012 | 非正常可关联状态 | 不推断含义，不作为关联源 |

历史显示：差旅报销完成并进入已付后，对应申请通常由系统自动变为 `closed=true`。skill 不主动关闭申请。

## 差旅申请 → 差旅报销

关系不是单字段，而是三个同步表面：

```text
expense report
├─ applicationOID / applicationBusinessCode / applicationFormOID
├─ expenseReportApplicationDTOS[0]
│  ├─ applicationOID / applicationBusinessCode / applicationFormOID
│  ├─ travelStartDate / travelEndDate
│  └─ relatedSimpleApplicationInfo
└─ applicationStartAndEndDateMap
   ├─ <applicationOID>+start_date
   └─ <applicationOID>+end_date
```

`custFormValues` 的“关联申请”字段在历史详情中可以是 `null`，因此不能用它判断是否关联成功。

### 日期差异

同一个业务日期在两类对象中格式不同：

- 申请 `KSRQ/JSRQ` 和 `travelApplication.startDate/endDate`：中国时区转 UTC。
  - 2026-06-02 00:00 CST → `2026-06-01T16:00:00Z`
  - 2026-06-30 23:59 CST → `2026-06-30T15:59:00Z`
- 报销关联日期：本地墙上时间直接带 `Z`。
  - `2026-06-02T00:00:00Z`
  - `2026-06-30T23:59:00Z`

使用 `application_date_values()` 与 `report_date_values()`，不要手拼。

## 个人报销

个人报销不需要、也不存在申请单前置环节，与申请单完全解耦：

- `applicationOID/applicationBusinessCode/applicationFormOID = null`
- `expenseReportApplicationDTOS = []`
- `applicationStartAndEndDateMap = {}`

历史个人报销的发票可以分到“默认费用大类”“招待费”“福利费用”等多个大类，单据总额等于所有分组金额之和。

## 公司与部门

历史中出现过申请挂登录公司、报销挂票据抬头公司的情况。因此：

1. 发票抬头是报销公司选择的第一证据。
2. 近期同类报销是第二证据。
3. 申请单公司不能单独决定报销公司。
4. 部门、代理人、参与人应从近期历史和用户唯一匹配结果校准。

## 预算与报销金额

正常业务顺序是“出差前申请并审批 → 出差 → 关联报销”。当前因工作特点采用事后补流程：“先按实际票据创建并审批申请 → 再创建关联报销”。无论采用哪种顺序，只有差旅报销需要差旅申请；个人报销始终不需要申请。

历史关系支持“分类和金额通常一致”：

| 申请 → 报销 | 总额关系 | 分类关系 |
|---|---|---|
| 2026-04 | 完全一致 | 出差补贴、过路费、酒店逐项一致 |
| 2026-06 | 完全一致 | 金额逐项一致；`其他交通` 在报销中显示为 `市内交通费` |
| 2026-07 | 完全一致 | 出差补贴、过路费、酒店、其他交通逐项一致 |
| 2026-02 | 报销少 4,180.62 | 火车、过路费、酒店、市内交通逐项一致，仅出差补贴减少 |

因此，事后补申请时应先完成票据分类，以同一份差旅费用计划生成申请预算和报销费用。不能把“一致”写成绝对规则：实际报销减少、补贴调整或历史类别别名都可能造成差异，但必须逐类审计并说明。

申请资金明细存于 `budgetDetailDTO.budgetDetail[]`，每行包含费用类型、金额和分摊。构造新申请时，从历史同类型预算行复制结构，清除 `id/budgetOID/applicationOID/apportionmentOID` 等旧身份，并写入当前分类金额。若历史模板缺少所需类型则停止，不能猜测费用类型 OID。

## 发票与报销总额

`GET /api/v3/expense/reports/{oid}` 给出单据总额，但通常不返回费用行。费用行真值来自：

`GET /api/expense/report/invoices/v2?expenseReportOID={oid}`

验收等式：

```text
sum(invoiceGroups[].totalInvoiceAmount) == expenseReport.totalAmount
```

按货币精度比较，避免 `3775.3199999999997` 之类浮点展示误差。

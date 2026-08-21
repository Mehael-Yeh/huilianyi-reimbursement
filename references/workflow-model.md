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

个人报销与申请单完全解耦：

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

申请预算不等于报销金额：历史存在预算 12,851.93、最终报销 8,671.31 的实例。报销金额由已落账费用行计算，不能从申请总额复制。

申请资金明细存于 `budgetDetailDTO.budgetDetail[]`，每行包含费用类型、金额和分摊。当前纯 API 创建器只验证过零预算表头；在预算行创建未完成独立实测前，必须让用户确认或手工补预算。

## 发票与报销总额

`GET /api/v3/expense/reports/{oid}` 给出单据总额，但通常不返回费用行。费用行真值来自：

`GET /api/expense/report/invoices/v2?expenseReportOID={oid}`

验收等式：

```text
sum(invoiceGroups[].totalInvoiceAmount) == expenseReport.totalAmount
```

按货币精度比较，避免 `3775.3199999999997` 之类浮点展示误差。

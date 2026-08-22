# 申请与报销关系

## 状态约束

| 对象 | 状态 | 自动化动作 |
|---|---:|---|
| 申请单或报销单 | 1001 | 允许创建、编辑和增加费用 |
| 差旅申请单 | 1003 | 仅 `closed=false` 时允许关联差旅报销 |
| 已完成或已付款单据 | 其他终态 | 只读，不修改 |

报销完成后，关联申请可能由系统自动关闭；自动化不得主动关闭申请。

## 差旅申请与差旅报销

差旅报销关系必须同时写入：

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

`custFormValues` 中显示为“关联申请”的字段可能为空，不能单独用于判断关联是否成功。

申请日期按中国时区转换为 UTC；报销关联日期使用本地墙上时间并带 `Z`。统一调用 `application_date_values()` 和 `report_date_values()`，禁止手工拼接。

## 个人报销

个人报销不需要申请单，必须清空全部申请关系：

- 顶层申请 OID、单号和表单 OID 为 `null`。
- `expenseReportApplicationDTOS=[]`。
- `applicationStartAndEndDateMap={}`。

## 公司、部门与人员

1. 报销公司优先依据发票抬头和近期同类报销。
2. 申请公司不能单独决定报销公司。
3. 部门、代理人和参与人必须通过当前租户唯一匹配。
4. 无法唯一确定时要求用户确认，不沿用未经复核的历史 OID。

## 预算与实际费用

正常顺序为申请审批后发生差旅并报销；事后补流程仍应先完成申请审批，再创建关联报销。两种流程都遵循：

- 申请类别和金额是已知费用的预算基线，通常接近实际报销，但不要求完全一致。
- 预算类目是汇总池，同类多张发票共同关联该类目的全部预算行 ID。
- 申请中没有的停车费等实际类别使用空预算列表按真实类别保存。
- 实际金额与预算差额属于核对信息，不是强行改分类或拒绝保存的依据。

构造申请预算时，从历史同类预算行复制结构，清除旧身份字段并写入当前汇总金额。找不到费用类型模板时停止，不能猜测 OID。

## 总额验收

报销单总额来自报告详情，费用行来自：

`GET /api/expense/report/invoices/v2?expenseReportOID={oid}`

按两位小数验证：

```text
费用分组金额之和 = 报销单总额
```

同时按类别输出申请金额、报销金额、差额和费用数量，并写入 Excel 核对表。

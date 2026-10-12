# 表单字段语义

字段 OID、表单 OID 和费用类型 OID必须从当前租户或历史模板动态获取。本文件只记录稳定语义。

## 差旅申请单

| fieldCode | 含义 | 规则 |
|---|---|---|
| field_3917 | 费用承担公司 | 按历史/用户确认 |
| field_0001 | 费用承担部门 | 按历史/用户确认 |
| DLR | 代理人 | 唯一用户 OID |
| KSRQ / JSRQ | 起止日期 | 中国时区转 UTC |
| field_4963 | 是否总务订机票 | 否=`2` |
| MDD | 目的地 | 可选 |
| field_2572 | 单程/往返 | 总务不订票时可为 null |
| field_6796 | 研发项目 | 不确定则问；可选 |
| field_8159 | 交通工具 | 如“私车” |
| field_0004 | 参与人 | JSON 字符串数组 |
| field_1819 | 事由 | JSON 字符串数组 |

草稿顶层使用 `custFormValues`，不是旧文档中的 `customFormValueDTOList`。

## 差旅报销单

稳定字段：费用公司、费用部门、是否分摊、起止日期、项目、事由。关联申请的真实关系由顶层字段、DTO 和日期映射构成，见 `workflow-model.md`。

酒店费用字段：

- `入住城市`（LOCATION）：从酒店销售方名称/地址推断；多地 `showValue` 用中文逗号连接。
- `开始结束日期`（START_DATE_AND_END_DATE）：JSON 中写整张差旅报销的起止日期和含首尾的天数。
- `客户名称`：票据里没有这个信息。可以由用户提供后用 `--field 客户名称=...` 写入，或由技能从历史同类型费用行克隆字段定义后写入；两者都拿不到时留给用户补录，不填写占位文案。

这三类字段都来自 `POST /invoice/api/invoice/defaults`，该接口返回的是**裸字段列表**（不是 `{data: [...]}` 封装），且只有传**已查验**的 `invoiceInfo` 才会带出 `sellerCityCode`。把列表当成字典会静默丢掉全部字段，单据随后被平台标为「必填未输」。

过路费的通行单/汇总单写入费用顶层 `attachments`，不计入 `receiptList`，不重复计金额；`attachments` 同样接受 Excel（里程补贴、油费的私车公用里程表会自动附上）。

## 分摊字段（`expenseApportion`）

`POST /api/expense/default/apportionment` 只返回空壳模板：金额、币种、费用类型、单据 id、单据公司字段全为 null。对开启分摊的费用类型（其他招待费用、酒店）必须补齐后才能提交 V5，否则平台返回 HTTP 500 系统异常：

- `amount` / `baseCurrencyAmount` = 费用行金额；`originTaxAmount` / `baseTaxAmount` = 税额。
- `currency` = CNY；`expenseTypeId` = 当前费用类型；`expenseReportId` = 报销单 `id`。
- `apportionmentCompanyOID` / `Name` / `Code` 取报销单 `docCompany*`；`proportion` = 1，`defaultApportion` = true。
- `costCenterItems`（费用承担部门、项目）保留接口返回值，不要清空。

已存在的费用行无法再次查询分摊接口（返回 VALIDATION_ERROR），更新时复用该行存储的 `expenseApportion` 并把金额与税额按新金额重算。

## 个人报销单

稳定字段：费用公司、费用部门、是否分摊、费用相关人、项目、事由。必须清空所有申请关系。

## 新草稿模板规则

从近期同类型报销单 `GET /api/v3/expense/reports/{oid}` 复制完整实体结构，然后：

1. 清空服务端身份字段、审批字段、付款字段和旧费用行。
2. `status=1001`，金额归零。
3. 重置每个 `custFormValues` 的 `id/formValueOID/bizOID/createdDate/lastModifiedDate`。
4. 只修改本次确定的业务值。

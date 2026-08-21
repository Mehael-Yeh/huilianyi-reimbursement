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

## 个人报销单

稳定字段：费用公司、费用部门、是否分摊、费用相关人、项目、事由。必须清空所有申请关系。

## 新草稿模板规则

从近期同类型报销单 `GET /api/v3/expense/reports/{oid}` 复制完整实体结构，然后：

1. 清空服务端身份字段、审批字段、付款字段和旧费用行。
2. `status=1001`，金额归零。
3. 重置每个 `custFormValues` 的 `id/formValueOID/bizOID/createdDate/lastModifiedDate`。
4. 只修改本次确定的业务值。

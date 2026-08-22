# 费用类型

费用类型不能硬编码 OID。不同租户、公司、表单和配置可能返回不同 OID。

查询：

```http
POST /api/expense/type/byUser
Content-Type: application/json

{
  "companyOID": "<报销单docCompanyOID>",
  "formOID": "<报销单formOID>",
  "expenseReportOID": "<报销单OID>",
  "userOID": "<报销人OID>",
  "roleType": "TENANT"
}
```

按 `name` 精确匹配，并从响应取：

- `expenseTypeId` 或 `id`
- `expenseTypeOID` 或 `oid`
- `iconName`

常用语义映射：

| 发票类别 | 差旅报销费用类型 | 个人报销费用类型 |
|---|---|---|
| 通行费 | 过路费 | - |
| 住宿 | 酒店 | - |
| 打车/出租车 | 市内交通费 | - |
| 礼品、餐饮>40 | - | 其他招待费用 |
| 餐饮≤40 | - | 餐费 |
| 加油、油卡、油费/里程 | 按公司政策 | 里程补贴或油费（按近期历史） |

若同名类型返回多个结果或历史使用不同类型，向用户确认。

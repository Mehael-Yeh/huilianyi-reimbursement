# 单据字段映射（fieldCode/fieldOID，方案甲构造 draft payload 核心）

来源：`GET /api/custom/forms/field/list?formOID=<oid>`（纯 API 拉取）。字段以 `customFormValueDTOList` 提交：每个元素含 `{fieldOID, fieldCode, fieldName, value, required, fieldTypeId,...}`。

## 差旅申请单 formOID=OID_1
| seq | fieldCode | fieldName | 必填 | 类型 | skill 取值 |
|---|---|---|---|---|---|
| 0 | field_3917 | 费用承担公司 | REQ | 101 | 公司OID `OID_2` |
| 10 | field_0001 | 费用承担部门 | REQ | 101 | 树脂销售（部门OID待查） |
| 20 | DLR | 代理人 | REQ | 101 | 审批人甲/审批人乙（userOID；≠参与人，冲突问询） |
| 30 | KSRQ | 开始日期 | REQ | 103 | 起 |
| 40 | JSRQ | 结束日期 | REQ | 103 | 止（用户指定） |
| 50 | field_4963 | 是否总务订机票 | REQ | 106 | 否 |
| 60 | MDD | 目的地 | opt | 107 | 城市 |
| 70 | field_2572 | 单程/往返 | REQ | 106 | 往返（选"否"时UI隐藏，payload可能需按条件） |
| 80 | field_6796 | 研发项目 | opt | 101 | 无/空 |
| 90 | field_8159 | 交通工具 | REQ | 101 | 私车 |
| 100 | field_0004 | 参与人 | REQ | 101 | 示例用户 userOID |
| 110 | CYR | 出差人 | opt | 101 | - |
| 120 | field_0005 | 事由(旧) | opt | 101 | - |
| 130 | field_1819 | 事由 | REQ | 101 | 客户拜访 |

## 差旅报销单 formOID=OID_3
| seq | fieldCode | fieldName | 必填 | 类型 | 备注 |
|---|---|---|---|---|---|
| 0 | field_2493 | 关联申请 | REQ | 122 | **关联差旅申请单单号/OID** |
| 10 | field_7184 | 费用承担公司 | REQ | 101 | 公司OID |
| 20 | field_0001 | 费用承担部门 | REQ | 101 | 树脂销售 |
| 30 | field_8602 | 是否涉及分摊 | REQ | 106 | 否 |
| 40 | field_7882 | 分摊审批人 | opt | 101 | - |
| 50 | field_7800 | 开始日期 | REQ | 103 | |
| 60 | field_4242 | 结束日期 | REQ | 103 | |
| 70 | field_1978 | 项目 | opt | 101 | 无 |
| 80 | field_0002 | 事由(旧) | opt | 101 | - |
| 90 | field_2250 | 事由 | REQ | 101 | 客户拜访 |

## 个人报销单 formOID=OID_4
| seq | fieldCode | fieldName | 必填 | 备注 |
|---|---|---|---|---|
| 0 | field_1410 | 费用承担公司 | REQ | 公司OID |
| 10 | field_0001 | 费用承担部门 | REQ | 树脂销售 |
| 20 | field_2189 | 是否涉及分摊 | REQ | 否 |
| ... | （四字段后因 seq=None 未全部打印，可再 dump 补全） |

## 下一步
1. 记录每个字段的 **fieldOID**（draft payload 需要；dump 时一并输出）。
2. 构造 `customFormValueDTOList` payload → POST `/api/travel/applications/draft`（申请单）、`/api/expense/reports/custom/form/draft`（报销单，需传 formOID）。
3. 发票上传 multipart + OCR（`/api/v1/upload/attachment/multiple/init+finish`、`/api/v1/document/ocr/invoice/scan`）。
4. 绑定发票到明细行 + 差旅报销单关联申请单。

## ✅✅ 打通：差旅申请单草稿纯 API 创建成功（2026-08-20 实测 201）
关键：payload 必须带 **`travelApplication`** 对象（含 startDate/endDate）——这就是"开始时间未填写(16040)"的答案。post 到 `POST /api/travel/applications/draft`，返回 201 + applicationOID。

### 信封结构
```json
{ "formOID":"<差旅申请单OID>",
  "applicantOID":"<示例用户64f5f43a-...>",
  "customFormValueDTOList":[ ...字段数组... ],
  "travelApplication":{ "startDate":"2026-05-19T16:00:00Z","endDate":"2026-07-19T15:59:00Z",
      "departmentOID":"OID_5","departmentName":"树脂销售",
      "subCompanyOID":"OID_6",
      "bookingClerkOID":YEHAO,"bookingClerkName":"示例用户","hotelBookingClerkOID":YEHAO,"hotelBookingClerkName":"示例用户",
      "trainBookingClerkOID":YEHAO,"trainBookingClerkName":"示例用户",
      "manageType":1002,"carManageType":1002,"hotelManageType":1002,"trainManageType":1002,
      "carUniformBooking":false,"hotelUniformBooking":true,"trainUniformBooking":true,"journeyUniformBooking":true,
      "diningUniformBooking":true,"uniformBooking":true,"uniformReimbursement":false,
      "enableItineraryHead":false,"widgetItineraryMode":"single","participantNum":1,"travelDays":<天数>,
      "currencyCode":"CNY","companyCurrencyRate":1.0,"baseCurrencyAmount":0.0,"totalBudget":0.0,
      "externalParticipantNumber":0,"externalParticipants":[],"travelItinerarys":[],
      "travelItineraryBookingClerkDTOs":[],"userRankMap":{},"applicationOID":null },
  "applicationParticipant":{"applicationOID":null,"participantOID":YEHAO},
  "applicationParticipants":[{"applicationOID":null,"participantOID":YEHAO,"userOID":YEHAO,"fullName":"示例用户","companyOID":"1c38b0e8-..."}] }
```

### customFormValueDTOList 字段值格式（实测）
- field_3917 费用承担公司 = `OID_7`（不是公司OID，用此值）
- field_0001 费用承担部门 = `OID_5`（树脂销售 deptOID）
- DLR 代理人 = `OID_8`（审批人甲 userOID）
- KSRQ 开始日期 / JSRQ 结束日期 = ISO `"2026-05-19T16:00:00Z"`（开始=当日00:00CST→前日16:00Z；结束=当日23:59CST→当日15:59Z）。用户实际起止日期：如开始07-01 00:00、结束08-01 23:59 → `"2026-07-01T16:00:00Z"` / `"2026-08-01T15:59:00Z"`
- field_4963 是否总务订机票 = `"2"`（否=代码"2"）
- field_2572 单程/往返 = null（选否后无需填；如选是则填对应枚举码）
- field_8159 交通工具 = `"私车"`（字符串）
- field_0004 参与人 = `[{"userOID":"64f5f43a-...","fullName":"示例用户","participantOID":"64f5f43a-...","companyOID":"1c38b0e8-..."}]`（**JSON字符串**）
- field_1819 事由 = `[{"id":"<任意>","name":"客户拜访"}]`（**JSON字符串**）
- MDD 目的地=null, field_6796 研发项目=null（非必填，不填）

### 校验
- 读已存申请单详情：`GET /api/application/<entityOID>?showValue=true`（返回 travelApplication + custFormValues 完整结构，可反向学结构）
- 列申请单：`POST /api/applications/v4/search?roleType=TENANT&page=0&size=20`

## 报销单（差旅/个人）已探明结构（2026-08-20）
- 读已存报销单详情：`GET /api/v3/expense/reports/<expenseReportOID>`（返回 data.rows[]，含 custFormValues + expenseReportApplicationDTOS 关联申请 + expenseDetail 明细）
- 列报销单：`POST /api/expense/reports/search/my?page=0&size=20`（OID 键 = `expenseReportOID`）
- **差旅报销单** formOID=`OID_3` 字段值：
  - field_2493 关联申请(REQ)：关联差旅申请单（另有 expenseReportApplicationDTOS 数组链 applicationOID/applicationBusinessCode）；存过值 null
  - field_7184 费用公司=`589c1869-...`；field_0001 部门=`23ee3003-...`
  - field_8602 是否分摊=`"N"`
  - field_7800/4242 开始/结束日期=`2026-05-01T00:00:00Z`/`2026-06-01T23:59:00Z`
  - field_2250 事由=JSON串 `[{"id":"...","name":"客户拜访"}]`；field_1978 项目=项目OID（如`83e38312-...`，可选）
- **个人报销单** formOID=`OID_4` 字段值：
  - field_1410 费用公司=`589c1869-...`；field_0001 部门=`23ee3003-...`；field_2189 是否分摊=`"N"`
  - field_2369 费用相关人=JSON串 `[{"userOID":"64f5f43a-...","fullName":"示例用户","participantOID":"..."}]`
  - field_1875 项目 可选(项目OID)；field_0002 事由=`"客户拜访"`
- **draft 信封（进行中，未打通）**：`POST /api/expense/reports/custom/form/draft?corporateFlag=false`
  - 已试：formOID 放顶层→500系统异常(无论字段多精简/完整、expenseReport是否带formOID/detail)；formOID 仅放 expenseReport 内→400"申请人无单据null的创建权限"(formOID读为null)。→ 断言：formOID 必须顶层，但顶层后处理报销单主体时 500，说明**POST 请求体整体形状仍未知**（非字段问题）。
  - 已探明细：从真实草稿 ERxxxxx 反推字段值(+messageKey/fieldType已在参考)：费用公司=select_company、部门=select_department、分摊=cust_list"CUSTOM_ENUMERATION"、"N"、费用相关人=select_participant、分摊审批人=select_user、项目=select_cost_center、事由=title。报销单挂**示例公司甲**(corporationOID=`OID_9`,setOfBooksId=`1483617793285816321`)，非浙江佑谦。个人报销单无 expenseReportApplicationDTOS。
## ✅✅✅ 差旅报销单创建+关联申请单 纯API打通（2026-08-21 实测 200）
- **ERxxxxx** (expenseReportOID=2a392930-…, formOID=489e9a03) 关联已审核申请单 **TZxxxxx**(applicationOID=db2b5637, 6.2-6.30, 预算2000=酒店1000+过路1000)。
- **配方**：读已存差旅报销单(如 ERxxxxx)v3 详情→行实体=tpl(153键)→空 expenseReportOID/entityOID/businessCode/id/createdDate/bizOID → **`expenseReportApplicationDTOS`**=[{applicationOID, applicationBusinessCode, applicationType:1002, applicationFormOID:9c906462, travelStartDate/EndDate, travelDays, participantNum}] → custFormValues 设 **`EXPENSE_REPORT.applicationOID`**(关联申请字段, value=applicationOID) + 开始/结束日期(按 fieldName) → 清发票/明细数组 → `POST /api/expense/reports/custom/form/draft?corporateFlag=false` 200。
- **关键字段code**：差旅报销单 custFormValues 用 `EXPENSE_REPORT.applicationOID`(关联申请)/`docCompanyOID`(公司)/`departmentOID`(部门)/`title`(事由)，**不是 field_XXXX**。
- 状态码：申请单 1001=草稿、**1003=已审核通过**(可关联)；报销单 1001=草稿、1005=已付。
- 待补：差旅报销单**费用明细**(酒店/过路费)落账——同"收据池id"墙。
- TZxxxxx OID=OID_10，KSRQ=2026-06-01T16:00:00Z(06-02 00:00CST)/JSRQ=2026-06-30T15:59:00Z，custFormValues=14已存。
- 待攻克：**资金明细（酒店/过路费）**——差旅申请单的费用/成本行结构（travelItinerarys 有 travelItineraryTraffics/travelElements 但都空；资金明细的确切落点/接口未定位）。行程列表路由待确认。
- 报销单落账：bag/details/add 200 但读报告 amount 仍0 → 需"存单"落账机制（把bag行随实体回存draft）。此为报销单全链最后一步。

## ⚠️⚠️ 关键修复（2026-08-20）：差旅申请单草稿必须用顶层 `custFormValues`
- **Bug**：旧配方用 `customFormValueDTOList` → 201 但字段值**没落库**，手机/钉钉端**打不开**（TZxxxxx 即此病）。
- **修复**：信封顶层要用 **`custFormValues`**（字段对象数组，每项含 fieldOID/fieldCode/fieldName/fieldType/value/**showValue**/messageKey/sequence…），不带 customFormValueDTOList。
- **已验证**：改用 custFormValues 后 TZxxxxx 存储正常（top-level custFormValues=14字段，与能开的 1833 一致）。脚本 `hly_tz_cf_fix.py`。
- 字段值 key 约定（照 1833/1834 模板，showValue 需填人类可读值）：费用承担公司 value=589c…/showValue=示例公司甲；部门 showValue=示例公司乙|树脂销售；代理人 showValue=审批人甲；参与人/事由=JSON串。
- 个人报销单本来就用的 row['custFormValues']=数组（对），不混淆。

## ✅✅✅ 报销单草稿纯 API 创建已打通（2026-08-20 实测 200）
**终极配方（关键！之前 400/500 的根源）：**
1. **`custFormValues` = 「完整元数据字段对象」的数组**（每个对象含 id/formValueOID/bizOID/name/showValue/valueCode/fieldConstraint/guiWidgetOID/businessFieldCode/categoryType 等全部键）——**不是 JSON 字符串！**
2. **body = 整个报销单实体**（含全部表头：status/sourceType/type/receiptCheckStatus/asyncStatus/... docCompanyOID/corporationOID/setOfBooksId/subCompanyOID 等 120 键），**不要删除/精简表头**。
3. 新建草稿：把服务端 id 字段（expenseReportOID/entityOID/businessCode/id/createdDate/bizOID/formValueOID 等）**置 None**，保留结构。
4. 端点：`POST /api/expense/reports/custom/form/draft`（返回 200 + expenseReportOID + businessCode）。
5. **最简单实现**：读一张已存报销单 v3 详情行 `GET /api/v3/expense/reports/{oid}`→ rows 即实体模板；把 custFormValues[i] 的值改成目标、id 字段置 None，直接作为 body POST。
6. 已验证：个人报销单 formOID=b5f8063b…、custFormValues 按 messageKey（select_company/select_department/cust_list/select_participant/select_cost_center/title）改 value 即可；事由 field_0002 messageKey=title。测试产 ERxxxxx。
7. 用户审批链/参与人/代理人同申请单；费用承担公司挂 docCompany（嘉兴锐石 589c1869…，docCompanyCode=rs，corporationOID=6cc93ab6…）。
- 用户确定：申请单"研发项目"非必填不填；参与人默认"本人"示例用户；代理人=审批人甲或审批人乙（审批人乙OID=`OID_11`）。

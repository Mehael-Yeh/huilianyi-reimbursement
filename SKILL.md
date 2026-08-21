---
name: huilianyi-reimbursement
description: "触发:报销/差旅/汇联易/填报销单. 收发票→分类→建差旅申请单+报销单草稿(不提交)。"
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [汇联易, 报销, 差旅, 发票, huilianyi, helios]
    related_skills: [hermes-gateway-service]
---

# 汇联易报销填报 skill

自动化完成汇联易(Helios)报销资料填报：用户只交付发票 → 识别分类 → 建差旅申请单 → 建差旅报销单+个人报销单草稿，最后**由用户手动提交**。

## ⛔ 铁律（最高优先级，任何时候不得违反）
- **绝不提交（submit）任何单据**。
- **绝不删除（delete）任何用户单据**（含测试草稿，需用户处理或明确指示）。
- 只建 **草稿/编辑中** 状态；最终 **提交由用户在网页手动完成**。
- 报销字段值不够确定时，**向用户问询**，不猜。

## 🔑 登录（Step 1）
- 入口：`https://console-a2.huilianyi.com/`
- 方式：账号登录 tab → 手机号 `138xxxxxxxx` + 密码 + 勾选用户协议 → 登录
- 登录后后台：`https://console-a2.huilianyi.com/main/dashboard`
- 用户：示例用户 241202623 · 示例公司乙 | 树脂销售
- **掉登录处理（重要）**：浏览器会话不稳定，导航回登录页即重登（账号密码不变）。
- 若走方案甲（直连 API），登录=获取 token 绕过浏览器。

## 🆕 Step 1.5：登录后先读历史单据校准基础数据（必做）
每次为新用户/新任务填表前，**先向用户申请读取其过去 3 张申请单 + 3 张报销单**（列表 + 详情），用来校准本套单据的**基础填写数据**，避免凭假设填错：
- **费用承担公司归属**：有的客户申请单/报销单挂**示例公司甲**（corporationOID=`OID_1`，费用承担公司=589c1869…，showValue=嘉兴锐石；login 公司却是浙江佑谦），有的挂浙江佑谦/其他。**必须读历史确认本次挂哪家**。
- 费用承担部门（如树脂销售 deptOID=`23ee3003-…`）、代理人、参与人习惯、事由措辞、项目(select_cost_center)、是否分摊取值。
- 读法：纯 API `POST /api/applications/v4/search`（申请单）/ `POST /api/expense/reports/search/my`（报销单）列最近，再 `GET /api/application/{oid}?showValue=true` / `GET /api/v3/expense/reports/{oid}` 看详情。
- 若用户提供了票据，按其发票抬头匹配归属公司；不确定就**问询**。

## 📁 环境与前置
- 发票分类引擎（用户自有）：`/vol1/@appdata/trim.hermes/workspace/Invoice-Set/`
  - venv：`.venv`（已装 pypdf/openpyxl/reportlab）
  - 分类：`.venv/bin/activate && python invoice_organizer.py --scan <发票文件夹>` → JSON
  - 整理：`--organize <dir> --output <dir>` → 文件夹+Excel
  - 测试发票脚本：`tests/generate_fixtures.py`；样例：`tests/fixtures/`（8类）
- 发票交付（用户任选）：微信/图片/PDF/压缩包/NAS 路径。PDF 走引擎；图片另用 OCR 或汇联易自带识别。

## 🧾 发票识别与分类（Step 2）
用 Invoice-Set 引擎，规则：
- **1.差旅报销**：过路费 / 酒店 / 停车费 / 打车费(含代驾) / 其他交通(铁路·飞机)
- **2.个人报销**：餐费 / 礼品费 / 里程补贴(油费)
- **餐费 >80元 → 礼品费**；80元整仍餐费
- "生产生活服务"细分：通行费/过桥过闸→过路费，停车→停车费，餐饮→按80元
- 打车行程单/通行费汇总单归档不计金额；重复发票只计一次(进待核对)
- 发票抬头应为 **示例公司甲**（≠开户公司浙江佑谦，同集团）
- 输出按 差旅组 / 个人组 分开（金额、张数、日期区间）

## 📝 差旅申请单（Step 3）
入口：申请单模块 → 新建申请单 → 差旅申请单
固定取值（用户确认）：
- 费用承担公司：示例公司乙
- 费用承担部门：示例公司乙|树脂销售
- 是否总务订机票：**否**（选否后"单程/往返"字段自动隐藏，无需填）
- 研发项目：无（无则留空/问询）
- 交通工具：**私车**
- 事由：**客户拜访**
- 目的地：可选（客户所在城市）
- 起止日期：**结束日期由用户指定，须提问**
- 代理人：一般选 **审批人甲** 或 **审批人乙**；与参与人冲突则问询
- 参与人：**必须问询**；当前用户选 "示例用户"

## 📄 报销单（Step 4）
入口：报销单模块 → 新建报销单 → 差旅报销单 / 个人报销单
- **差旅报销单**：**必须关联 Step3 差旅申请单**（如 TZxxxxx）。费用三块：贴票(有票)、无票(出差补贴·列客户名)、免贴票。
- **个人报销单**：不关联申请单。费用如里程补贴/其他招待费用。
- 发票上传后由汇联易 OCR 识别，归入费用明细行。
- 事由：如"客户拜访"/"客户送礼，请客招待"。
- 审批流（核对用）：示例用户→审批人乙(主管)→审批人丙(总监)→审批人丁(收单/审核)→审批人戊→审批人己(经理)→审批人庚(出纳)。

## 🏗️ 方案甲（直连 API，推荐；✅ 全流程配方已打通，2026-08-20 实测）
登录→建差旅申请单草稿(201)→建个人报销单草稿(200)→发票上传→OCR识别(`/receipt/api/receipt/ocr/v3`)→查验→类别匹配→分摊→invoiceOID→绑定，全部纯 API 配方见 `references/api-endpoints.md`。
**完整一套实测**：差旅申请单 TZxxxxx + 个人报销单 ERxxxxx（编辑中草稿，未提交）。
**已完成（2026-08-20 纯 API 实测）：**
- ✅ 登录：RSA-2048 加密密码 → OAuth2 password grant → access_token（见 `references/api-notes.md` + `scripts/hly_login.py`）
- ✅ 读数据：`/api/account`、`/api/expense/reports/search/my` 均 200
- ✅ 端点地图：`references/api-endpoints.md`
- ✅ 单据 formOID + **全部字段 fieldCode/fieldOID/必填**：`references/form-fields.md`
- ✅ 建单信封有效：`POST /api/travel/applications/draft` 携 `{formOID, applicantOID, customFormValueDTOList:[{fieldOID,fieldCode,fieldName,value,...}]}` 到达服务器、返回字段级校验错误（证明结构被识别）
- 已解析 OID：公司=`OID_2`；示例用户=`OID_3`；审批人甲=`OID_4`

**剩余（路线2，纯API收尾）：**
1. 日期系统字段：建单报 `开始时间未填写(16040)`——日期是系统级字段，非普通值；需按候选系统字段名（startTime/endTime/outboundDate/returnDate 等）试探，或抓真实保存请求确认。
2. 枚举 OID：是否订机票=否、单程往返=往返、交通工具=私车、事由=客户拜访 的 option OID（`/api/custom/enumerations/` 系列可查）。
3. 费用承担部门（树脂销售）OID。
4. 发票上传：`/api/v1/upload/attachment/multiple/init+finish`、`/api/upload/attachment`、`/api/v1/document/ocr/invoice/scan`、绑定 `/api/v1/img/business/attachment/invoice/bind`（实测）。

**脚本（workspace/Invoice-Set/tests/）：** hly_login_test.py / hly_api_test.py / hly_forms.py / hly_fields_dump.py / hly_refs.py / hly_draft1.py / hly_draft2.py

## 🏗️ 方案乙（浏览器自动化，兜底）
- 若纯 API 卡在**日期系统字段**或**发票上传** → 退回浏览器完成建单+上传（登录/读/字段定义等方案甲成果仍复用）。
- 浏览器会话不稳（远端/无持久 profile）会掉登录：检测到登录页即自动重登。
- 注意：浏览器里 antd 组件用 JS 点击不被 React 识别（选人显示"已选 0 条"），填表需用真实鼠标事件（browser_click 系列）逐项点选，较费劲。

## ⚠️ 待明确/待验证
1. 差旅申请单日期系统字段的确切 field 名/位置（路线2关键）。
2. 枚举值 OID（否/往返/私车/客户拜访）。
3. 费用承担部门（树脂销售）OID。
4. 差旅报销单"关联差旅申请单"(field_2493) 的取值结构。
5. 发票文件上传 multipart 实测（方案甲关键）。
6. 已建的测试草稿（浏览器里"编辑中"那份）需用户确认处理（不删除）。

## 参考文件
- `references/invoice-classification.md` — 分类密钥词与规则
- `references/api-notes.md` — 登录/鉴权完整配方（已打通）
- `references/api-endpoints.md` — 端点地图 + 表单 formOID
- `references/form-structure.md` — 历史 UI 结构调研（早期）
- `references/form-fields.md` — 三单据全部字段 fieldCode/fieldOID + 草稿实测结果

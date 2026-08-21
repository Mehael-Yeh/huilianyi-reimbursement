# 汇联易逆向/自动化技术笔记（session 沉淀）

来源：2026-08-20 长会话（方案甲纯API + 浏览器抓包试错）。目的：让下一次会话**不重蹈死路、接着上次进度走**。

## 已解决 & 可靠的（复用，别重来）
- 登录：RSA-2048(PKCS1 v1.5) 加密密码 → OAuth2 password grant → `access_token`（见 api-notes.md + scripts/hly_login.py）。公钥硬编码在前端 `helios72eb628932.app.js`（MIIBIj...，392字符）。
- 读数据：`GET /api/account`、`POST /api/expense/reports/search/my` 带 `Authorization: Bearer <token>` 均 200。
- 建单信封可达：`POST /api/travel/applications/draft` 携 `{formOID, applicantOID, customFormValueDTOList:[{fieldOID,fieldCode,fieldName,value,fieldTypeId,required,...}]}` 回**字段级校验错误** ⇒ 结构被识别、方向对。
- 场景脚本可复用：hly_forms / hly_fields_dump / hly_refs / hly_api_test（skill scripts/ 与 workspace/Invoice-Set/tests/ 各一份）。

## ⚠️ 技术坑：React(antd) 组件的自动化
- **简单 input（登录手机号/密码、交通工具文本框、日期框）**：用原生 setter + dispatch input/change 能生效：
  ```js
  const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; s.call(el,v);
  el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));
  ```
- **antd 下拉/选人（是否订机票、代理人、参与人、事由）**：`.click()` 或纯 JS 事件**不被 React 识别** —— 表单校验仍报"XX 不能为空 / 已选 0 条"。必须用**真实 CDP 鼠标事件**（browser_click 系列）点开、再点选项；即便如此，选人(人员 dialog)也可能点不开/不响应。→ 与其死磕浏览器填表，不如靠**后端抓真实包**或**纯 API 按字段 OID 构造**。
- 浏览器会话（Browserbase 远端）会掉登录：导航回登录页即需重登（账号密码固定）。

## 🔒 当前未解决障碍（下次接着从这里走，别重复瞎猜）
**差旅申请单草稿被拦："开始时间未填写"(errorCode 16040)。**
- 已试均失败：customFormValueDTOList 里 KSRQ/JSRQ（开始/结束日期）取值 ISO、epoch毫秒、`2026-05-19` 字符串；顶层 startTime/endTime(iso/ms)、travelStartDate/travelEndDate、startDate/endDate。
- 结论：该"开始时间"是**独立系统级行程字段/子表**，不在上述任意位置；盲猜字段名不收敛。
- **推荐的下一步（用户认可路线 A）**：让用户（本机浏览器从不掉线）手动新建并**保存**一张差旅申请单草稿（不提交），Hermes 用已打通的纯 API token 从后台/日志抓这次真实 `POST /api/travel/applications/draft` 的完整 JSON → 得到"开始时间"字段的确切名/层级 → 用纯 API 复现成功。
- 备选：B) 翻前端差旅表单路由 chunk 读前端构造 payload 源码；C) 纯 API 盲试（已证明不收敛，避免）。
- 其后剩余：枚举 OID（否/往返/私车/客户拜访）、费用承担部门(树脂销售)OID、差旅报销单 field_2493 关联申请取值结构、发票上传 multipart(`/api/v1/upload/attachment/multiple/init+finish`)+OCR(`/api/v1/document/ocr/invoice/scan`)+绑定(`/api/v1/img/business/attachment/invoice/bind`)。

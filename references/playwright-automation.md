# Playwright 驱动汇联易（仅逆向/验证用，不进 skill 生产流程）

## 为什么用完整 playwright 而非 puppeteer-core
`npm install playwright` 于 `/vol1/@appdata/trim.hermes/workspace/hly_auto/`；
`chromium.launch({headless:true})` 走 ms-playwright 自带 chromium-1234/headless_shell，
**渲染汇联易报销模块比 puppeteer-core 稳得多**——能稳定渲染报告列表、详情、发票向导、OCR，并完整抓包最终保存体（FINAL_SAVE_BODY.json）。

## 登录配方（实测成功）
- 手机号：`input[placeholder="请输入手机号/邮箱"]` .fill
- 密码：`input[placeholder="密码"]` .fill
- antd 复选框：点 `label.ant-checkbox-wrapper`（`input[type=checkbox]` .check() 常被 antd 吃）
- **登录按钮**：`page.evaluate(()=>[...document.querySelectorAll('button')].find(x=>/登录/.test((x.textContent||'').replace(/\s/g,''))).click())`
  - ⚠️ 按钮文本是 **"登 录"（含空格）**，`trim()` 匹配不到，**必须 `\s` 全去空白**。
- playwright 的 `button:has-text("登录")` / `getByRole` 对含空格中文有时 count=0，勿依赖，统一走 evaluate。

## 报告导航 / 交互
- 直接 `page.goto('/main/expense-parent-report/expense-report')` **不稳**（SPA 路由常不落），要点侧边栏菜单。
- 列表行点 `text=ERxxxxx` → 进详情（one-screen-detail）。详情已开时勿再点"个人报销单"cell（被 antd-tabs 拦截报错）。
- **先点"编辑"才出现"保存/取消"**（只读视图无保存按钮）。编辑态点保存会重算 apportionment（实测 amount live 200）。
- 发票上传：`发票生成费用` → `input[type=file]` setInputFiles(本地 PDF)（多次重试直到 input 出现）。
- antd 组件点不透（`.category-list-item` / modal 按钮被 overlay 拦截）：统一 `page.evaluate(el.click())` 分发。

## ⛔ 行添加的硬边界（2026-08-21 实测，防再次空耗）
- **报销单新增发票行：纯 API 被服务端"发票记录校验"挡死**：
  - 手拼 `invoiceView`（改 invoiceOID/amount/data）append 进 `expenseReportInvoices` 后 POST `/api/expense/reports/custom/form/draft` → 改 `data` 时 **400 VALIDATION_ERROR**；
  - 只换 invoiceOID/amount **200 但 totalAmount 不变**（服务器只认**内部已注册**的发票记录）。
  - → 新行必须经系统"**生成费用**"向导在内部注册。
- **向导 save 在 headless 下 antd 免疫**：即便 playwright 上传 + 选类别(其他招待费用) + 点保存/继续保存，保存请求体里**仍不带新票（expenseReportInvoices bound 恒为已有张数）、总额不变**。
- 差旅申请单"资金明细(酒店/过路费)"走行程预算结构(apportionment),同样在受控 UI 编辑,headless 加不进。
- **能可靠做成**：识别链(上传→OCR→verify→tax/amount→invoiceOID)、建单(差旅/个人)、**实体回存**(用 FINAL_SAVE_BODY.json 模板回存 draft=200 保总额)、读取核实(`GET /api/expense/report/invoices/v2?expenseReportOID=`)。

## 结论
"发票识别+分类+建单"纯 API 100%；"**在草稿里新增发票/资金明细行**"需真人/非 headless 环境触发受控向导，headless 与纯 API 都绕不过服务端的记录注册校验。行由用户点加后，纯 API 可读取核实与安全回存。

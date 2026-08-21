# 汇联易 API 端点地图（方案甲逆向，从主 JS bundle 提取）

来源：`helios72eb628932.app.js`（static2.huilianyi.com/helios/）。鉴权统一 `Authorization: Bearer <access_token>`，基址 `https://api-a2.huilianyi.com`。

## 差旅申请单
- 保存草稿：`POST /api/travel/applications/draft`
- 提交：`/api/travel/applications/submit`、`/submit/v2`（**勿用，用户手动提交**）
- 城市风险检查：`/api/travel/application/city/risk/check`

## 报销单（差旅报销单/个人报销单）
- 保存草稿：`POST /api/expense/reports/custom/form/draft`（自定义表单报销单）
- 通用申请单草稿：`/api/public/applications/draft`、`/api/expense/applications/draft`
- 提交：`/api/v3/expense/report/submit`（**勿用**）
- 查询列表：`POST /api/expense/report/search`、`/api/expense/reports/search/my`
- 生成 PDF：`/api/expense/reports/generate/pdf/`
- 费用分块 apportionment：`/api/v3/expense/default/apportionment`
- 费用包加明细：`/api/expense/reports/bag/details/add`

## 发票上传（已打通，2026-08-20 实战 5 张真 PDF）
- **端点**：`POST /api/upload/attachment`（multipart）
- **格式**：`attachmentType=INVOICE_IMAGES` + `file=<发票文件>`（字段名必须 attachmentType+file）
- 响应：`attachmentOID`（+ id/fileName/fileURL）
- 实测：真实电子发票 PDF 5 张全部上传成功（返回 attachmentOID）。**公司不允许上传图片**→只测 PDF/OFD，不测图片。
- 分片备用：`/api/v1/upload/attachment/multiple/init`→`/multiple/single?…`→`/multiple/finish`
- 其它：`/api/common/upload`、`/api/v1/attach/pool/upload`

## 发票来源：mehaelyeh@agent.qq.com（QQ 邮件，可读）
- 用 agently-cli（`export PATH=/vol1/@appcenter/nodejs_v24/bin:$HOME/.npm-global/bin:$PATH`）。**--output 必须相对路径**（如 `.`）。限频 10次/分，下载需逐个+sleep~7s。
- 电子发票邮件=`.eml`∈内嵌 PDF/OFD/XML；用 python `email` 库解 MIME 提取（数电票 PDF 名常含票号+购方名）。
- 真实样本已存 `/vol1/@appdata/trim.hermes/workspace/hly_invoices/`（clean/ 5张真PDF：小杨生煎x2/老上于518/12306订餐/常州159；extracted+imgs 含 OFD/HTML图）。

## ✅✅✅ 发票识别（OCR）纯 API 已打通（2026-08-20 验证 200）
**之前 404 真相**：OCR 不在 `/api/v1/document/ocr/*`，而在 `/receipt/api/receipt/ocr/v3`（收据微服务前缀）。熟悉的 `api-a2` base 直接可调！

**完整发票识别管线（全部纯 API 已验证）：**
1. **上传**：`POST /api/upload/attachment`（multipart attachmentType=INVOICE_IMAGES + file）→ 返回完整 attachment 元数据
2. **OCR 识别**：`POST /receipt/api/receipt/ocr/v3?client=WEB&isInternationalOCR=false&districtCode=&reportOID=<expenseReportOID>`
   BODY：`[{"oriAttachment":{<上传响应的完整 attachment 对象>}}]`
   → 200 `rows.receiptList[0]`：type/payee/fee(=分)/title(抬头)/draweeNo/billingNo/billingTime/feeWithoutTax/tax 等全部发票字段
3. **查验**：`POST /receipt/api/receipt/verify/batch`（OCR 结果数组）→ "查验成功，发票一致"
4. **总额**：`POST /invoice/api/receipt/cal/total_amount?newFlag=true`（receiptViewDTOList）→ totalAmount
5. **费用类别匹配**：
   - `GET /api/expense/types/category?levelCode=ALL`（费用类别树）
   - `POST /api/expense/type/byUser` `{companyOID,expenseReportOID,userOID,receiptList:[识别结果]}` → 用户可用费用类型
   - `POST /api/invoice/history/record/v2` `{receipts:[{receiptTypeNo,taxCodes}],expenseReportOID,createManually:true,withReceipt:"Y",reportDepartmentOID,userOID,page:0,size:1}` → **按发票匹配历史费用类型**（实测 餐饮票 → "其他招待费用" expenseTypeOID=OID_1 / id 1704675864861536258）
6. **费用类型详情**：`GET /api/expense/types/select/<expenseTypeId>`
7. **发票默认**：`POST /invoice/api/invoice/defaults?isDateCombinedUTC=false` `{expenseTypeId, receipts:[识别结果]}`
8. **费用分摊/分配**：`POST /api/expense/default/apportionment` `{expenseReportOID, expenseTypeId, amount, currency:"CNY", ownerOID, merge:true, applicationCustomBudgetId:[], prepaymentLineIdList:[], paymentCompanyOID}` → apportionment（相关人示例用户/费用承担部门）
9. **生成识别发票记录 invoiceOID**：`POST /invoice/api/invoice/tax/amount/by/receipts` `{amount, receiptList:[识别结果]}` → **rows.invoiceOID**（实测 2d900b3f-…）（draft 时此 invoiceOID 即 /api/expense/report/invoices/import 所需的 invoiceOID）
- 附：`/api/expense/report/invoices/import`（导入发票到单据；需已识别的 invoiceOID）
- base 全部可用 `api-a2.huilianyi.com`（OCR/初审在 console-a2 网关下 /receipt/ /invoice/ 前缀，api-a2 也可直调，已验证）。

## 逆向工具（仅测试用，不进 skill 流程）
- 本地 Chromium：`~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome` + puppeteer-core（项目 `/vol1/@appdata/trim.hermes/workspace/hly_auto/`，脚本 cap_flow.js）
- 用它走真实 UI 抓包（发票生成费用→uploadFile 本地 PDF→OCR→类别），提炼纯 API 配方。
- **skill 最终方案 = 纯 API；Chromium 只是逆向/验证工具，不依赖。**

## 已建测试单据（你账上，勿删，均编辑中未提交）
- 差旅申请单 TZxxxxx（纯API 201）
- 个人报销单 ERxxxxx（纯API 200）
- 你手动建：差旅申请单 TZxxxxx、个人报销单 ERxxxxx
- 已上传真发票附件OID：小杨生煎A cc3fe20d…、B 77b89db0…、12306 e13bb0ae…、常州70eb011e…、老上于3e72e04f…、重传小杨生煎A c19827c3…

## ✅✅✅ 发票→invoiceOID 全识别链已纯 API 打通（2026-08-21，5张全成）
**收据池之谜破解：`/receipt/api/receipt/verify/batch` 的响应就带 receiptOID！**
链路: 上传→OCR(`/receipt/api/receipt/ocr/v3`)→**verify(`/receipt/api/receipt/verify/batch` 用响应[0].invoiceInfo=enriched带receiptOID)**→**tax/amount(`/invoice/api/invoice/tax/amount/by/receipts`,body含amount/receiptList[enriched]/originalAmount/currencyPrecision:2/expenseTypeId/withReceipt/data[]/expenseReportOID)→200 invoiceOID**。5餐饮票全成(33/49/8/159/518→各invoiceOID)。之前500根因=没把verify响应传给tax/amount。
- ⛔ 建**费用明细行**端点候选：`/api/expense/reports/bag/details/add`(费用包加明细) — 待实测。
- **实测**（2026-08-21）：`POST /api/expense/reports/bag/details/add` body `{expenseReportOID, expenseTypeId, amount, currency:"CNY", expenseDate, relevantPersonOID, invoiceOIDs:[invoiceOID], receiptOIDs:[]}` → 200 true（5行各200）。**但读报告 amount 仍 0** → 行进的是工作态，需再"存单"(draft/save) 才落库；如何把 bag 行随存单持久化是最后的收尾点（若行接口 + 存单接口串好即 FULL DONE）。

## ✅ 发票重复上传 & 删除（2026-08-21 实测）
- **重复上传防重**：`POST /invoice/api/v5/invoices` 对被绑定发票返 `E_DUP`（"发票可报销总额不足，费用金额超出51.5"）拒绝；删除后可重加。
- **删除发票**：`DELETE /api/expense/reports/delete/invoice/{expenseReportOID}/{invoiceOID}` → 200 移除。**参数是 invoiceOID，不是 expenseReportInvoiceOID**（用 ERI 返回 404 OBJECT_NOT_FOUND / 对象没有找到）。
- `remove/invoice`（软删，200 但不真正移除）vs `delete/invoice`（硬删，生效）。删除前 check：`GET /api/expense/report/delete/check/invoice?expenseReportOID=` → BACK_BOOK(可账本导入)/DELETE_ALL(不可恢复)。
- 批量：`POST /api/expense/reports/delete/invoice/batch/{oid}` body=数组；收据池：`/receipt/api/receipts/delete/batch/byId`。
- ## ✅ 删除报销单（2026-08-21 实测 200）
  - **`DELETE /api/expense/reports/{expenseReportOID}`** → 200 `{"validateResult":null}`，删报告及其发票/费用记录（=“同时删除”）。
  - 实测删： ERxxxxx(58b691d8)、 ERxxxxx(2a392930)。前端 deleteExpenseReport / 批量 `/api/expense/report/batch/delete/{...}`。
  - 弹窗“单据删除后无法恢复”：退回账本=发票留账本可复用；同时删除=发票一并删（避免与重传发票 E_DUP 冲突）。用户默认“同时删除”。
  - 仅当用户明确批准时删（铁律：不删用户数据）。

## ✅ 真实操作验证（用户 2026-08-21）
- 用户在 ERxxxxx 上真实完成"生成费用+保存"：**totalAmount=134，绑定 1 张招待费发票(invoiceOID=940d43d1)**，invoiceGroups 按类别分组(招待费),proportion100%。
- 明细/发票行加载端点：**`GET /api/expense/report/invoices/v2?expenseReportOID=<oid>`** → rows{expenseReportInvoices, invoiceGroups, invoiceViewDTOMap}。
- 结论：落账 = 绑定发票(expenseReportInvoices含invoiceOID+类别) + **存单**；bag/details/add 只是辅助。纯API"加行+存单"的把绑定+实体回存 draft 串好即 FULL DONE（此配方在本 session 末端已逼近，但"自动逐行生成+最终保存"仍需一次真实保存请求做对照闭环）。

## ✅✅✅ 官方落账流程（用户亲授，2026-08-21）+ 实测结果
**操作序列**：发票生成费用 → 识别发票文件 → **选择费用类型** → **保存** →（若提示"必填字段未填写"）→ **继续保存**。
**实测（用户真实操作）**：ERxxxxx 现 **273 元**（134+139），**2 张招待费发票已绑定**（a7ccf160… 新 + 940d43d1… 原），invoiceGroups 按类别"招待费"分组 total=273，expenseReportInvoices 各含 invoiceOID+expenseReportInvoiceOID+status=1000。
- 读导入后发票/分组：`GET /api/expense/report/invoices/v2?expenseReportOID=<oid>` → rows.expenseReportInvoices / invoiceGroups / invoiceViewDTOMap。
- **闭环节点**：发票落账=绑定 invoiceOID 到 expenseReportInvoices + 选费用类型 + 保存/继续保存。纯API若要复刻，需构造「绑定 invoiceOID + 类别 + 存单」的请求体（识别链已给 invoiceOID，唯一待补=这条最终保存请求体本身）。

## ✅ chromium 落账尝试（2026-08-21，接近但未全通）
- **编辑模式才有"保存"**：打开报销单→点"编辑"→才出现 保存/取消；只读视图无保存按钮。
- 编辑态点保存会重算 `apportionment`(实测 amount=134 live 200)。ERxxxxx 保持 134 无损(1001 编辑中)。
- ⛔ 全自动"上传新票→选类别→落账→保存"仍失败点：编辑态下 `发票生成费用`→`input[type=file]` 上传input 时序/selector 不稳(uploadFile 未触发)，前端 antd 免疫。**完整落账保存请求体仍未抓到**。仅差此一步即可收口：需要一次真实"单票生成费用+保存"请求体做逐字段对照。

## ✅ 发票"替代类别"落账进差旅报销单（2026-08-21 实测）
- 用常熟水果receipt(id=209076) 替代成**过路费**落进差旅销单 **ERxxxxx**(2a392930): delete fruit from 3496 → v5(expenseReportOID=3499,expenseTypeName=过路费,id=1704675865738145793,oid=389132dd) → 200, invoiceOID=5434e5a2 绑定。**任意receipt+任意类别可落进任意报销单**(纯API)。
- 差旅类 expenseType: 酒店 id=1704675876349734914(oid 9fc05f34), 过路费 id=1704675865738145793(oid 389132dd), 市内交通费 1704675875397627905(4b58a40e)。
- **手录费用端点未明**: bag/details/add+apportionment(200不落库), manualCheck=收据人工核对(400类型不符)。真正手录"建行"端点待挖(藏法同v5,需真实操作浮出)。
- ## ✅⚠️ 纠错(2026-08-21 第3份HAR): v5 不需要数字 id!用户真实v5 `receiptList[0].id=None + receiptOID=897777a6`(上海云荷嘉餐饮过路费1150→3499,d9dda2e7) **成功200**。**纯API落账只需有效 receiptOID + verify→invoice/defaults→cal/total→tax/amount→v5 完整序列**。我此前"数字id"判断错。upload/attachment 需用 file.content base64+chunked 的正确返回。**
**真实保存不是 custom/form/draft，而是 `POST /invoice/api/v5/invoices`**（console-a2 基址，URL 带 hlyRequestID+roleType=TENANT+isDateCombinedUTC=false+utcTime=true+recalculateDeductible=true+needValidateExpBaseAmountOverReceipt=true）。
**请求体**：`{ownerOID, currencyCode:"CNY", expenseTypeName:"其他招待费用", expenseTypeOID:ed64b608…, expenseTypeId:"1704675864861536258", expenseTypeIconName:"trunckSupply", receiptList:[<完整富化发票>], invoiceCurrencyCode:"CNY", amount:49.0|51.5, expenseReportOID:<报告OID>, data:[]...}` → **响应返回 invoiceOID，直接绑定进报告**。
**receiptList[0] 必须含**：数字`id`(收据池DB主键,如209076…)+receiptOID+type+fee+payee+title(嘉兴锐石)+billingNo+billingDate+pdfUrl(有效oss签名)+taxString+cardsignTypeOCR+cardsignTypeList+checkPlatform(查验成功则QiXiangYun)+payeeNo+invoiceTypeNo113+uniqueCode+companyOID+invoiceGoods+…。
**全链**: upload→ocr→verify(响应invoiceInfo带id)→tax/amount→**v5/invoices**。列表刷新 = GET /api/expense/report/invoices/v2。
**当前纯API已通**: upload/ocr/tax→invoiceOID(=062f525c)。**唯一剩**: receipt 数字`id`(verify 对 小杨生煎B 返回 null；真实票 常熟 查验成功时生成 NATION 收据池记录带 id)。→ 数字id 由"查验成功建收据池记录"产生，需复现该步骤或用能查验成功的发票。
- **机制已 100% 破解**：落账=POST 完整实体+expenseReportInvoices(invoiceView)+totalAmount 到 `/api/expense/reports/custom/form/draft`。
- **新增行被服务端"发票记录校验"挡死**：手拼 invoiceView(改 invoiceOID/amount/data) 会导致 SAVE **400 VALIDATION_ERROR**；改少(仅换OID/amount)时 200 但总额不变(服务器只认内部已注册发票记录)。→ **新增发票行必须经"生成费用"流程在系统内部正确注册**，纯 API 无法用拼的 invoiceView 绕过。
- **可实现**：对**已绑定的发票**，重读 FINAL_SAVE_BODY(FINAL_SAVE_BODY.json) 回存 draft=200 保总额(不改行)。识别链(上传→OCR→verify→tax/amount→invoiceOID)纯API全通；建单(差旅/个人)纯API全通。
- 全流程结论：**"发票识别+分类+建单"纯API 100%；"把新发票行落账"需系统生成费用注册(前端手动/antd非headless)后,再纯API回存draft即可持久化**（FINAL_SAVE_BODY.json 即为回存模板）。

## ✅✅✅ 落账机制破解（2026-08-21 完整真值，playwright 抓包 FINAL_SAVE_BODY.json）
- **落账 = `POST /api/expense/reports/custom/form/draft`，body = 完整报销单实体，含 `expenseReportInvoices`（数组，每项 {expenseReportInvoiceOID, invoiceOID, status:1000, invoiceView}）+ totalAmount**。
- **`invoiceView` = 发票行完整结构**（~39键）：invoiceOID / **expenseTypeId / expenseTypeName(其他招待费用) / amount(139/134) / originalAmount / reimbursementUserId/Name/OID(报销人示例用户) / billingNo / payee / data(全票) / attachments / invoiceStatus** 等。
- **关键教训**：v3 读取会把 expenseReportInvoices 剥成 []，但**保存请求体里有它**——这就是 bag/details/add/apportionment 不落库的原因（它们不带这条数组），也解释了实体回存为何只存既有273。
- **纯API新增行方法**：取当前实体(或FINAL_SAVE_BODY模板)→在原 expenseReportInvoices 上 append 一条 `{invoiceView:{invoiceOID, expenseTypeId, expenseTypeName, amount, originalAmount, reimbursementUser, billingNo, payee, data}, status:1000}`→改 totalAmount(+新票金额)→POST draft 落账。
- 全流程纯API至此闭环：上传→OCR→verify→tax/amount(invoiceOID)→构造 expenseReportInvoices+totalAmount→draft保存。唯一待验：新增行(append)后保存是否成功(此机制刚破解,待实测一次)。

## 最终攻坚结论（2026-08-21 深夜）——诚实边界
- 已穷尽纯API(bag/details/add+apportionment+实体回存draft 全200但totalAmount不变)、chromium headless(渲染不稳/向导antd免疫)、xvfb(无root)、子模型×(2次撞上限无产出)。
- 前端 save 体(39341 chunk)形状：`{entityOID, entityType:1002, customFormValueDTOs: JSON.parse(custFormValues), recalculateSubsidy, ...} + 费用行以独立子存储`。费用明细行=独立子存储(expense_detail/bag_detail 表)，v3实体不序列化(invoices/v2 才有绑定发票)，用哪个端点把新行写入该子存储=唯一未闭合点。
- **ERxxxxx totalAmount=273(用户真实落账)，TZxxxxx(6.2-6.30)** 均正确在账。
- 收尾所需：一次真实"保存/继续保存"请求体(任何能正常渲染的浏览器网络面板)做逐字段对照。

## 已验证纯 API 能力状态（2026-08-20）
- ✅ 登录；✅ 建差旅申请单草稿(201)；✅ 建个人报销单草稿(200)
- ✅ 发票上传(PDF)→attachmentOID；✅ OCR(`/receipt/api/receipt/ocr/v3`)→全量发票字段
- ✅ verify富化(`/receipt/api/receipt/verify/batch`)；✅ 类别匹配(`/api/invoice/history/record/v2`)；✅ 分摊(`/api/expense/default/apportionment` 200)
- ⛔ **未打通：tax/amount→invoiceOID(500) + 生成费用落行+保存**
  - 缺失已定位：成功请求需 receipt 带 **`receiptOID`(收据池记录)** + 顶层 `originalAmount/currencyPrecision/expenseTypeId/withReceipt/data/expenseReportOID`。OCR后发票需先**落收据池**产生 receiptOID → 最后一段待攻克。
  - 成功请求真样本(got invoiceOID=2d900b3f…)存 /tmp/hly_js/cap_reqs.jsonl，含 receiptOID/attachmentOID/originAttachment/receiptType 等完整字段对照。

## 全链路攻坚状态（2026-08-20 深夜，全程纯 API+chromium测试抓包）
- ✅ 已纯API验证：填单(两张草稿)、上传、OCR、verify、类别匹配、**`/receipt/api/receipt/group/auto/1001`（分别生成费用→自动分组）**、`/api/expense/default/apportionment`。
- ✅ **tax/amount 确认可行**：前端向导内调用 `POST /invoice/api/invoice/tax/amount/by/receipts` 返回200 invoiceOID=76e9b6e4…。顶层参数 `{amount, receiptList, originalAmount, currencyPrecision:2, expenseTypeId, withReceipt:true, data:[], expenseReportOID}`。
- ⛔ **唯一剩余**：独立纯API调用 tax/amount 报500，因我的OCR receipt 缺**收据池富化字段**(receiptOID/tenantId/companyOID/formOID/entityType:"invoice"/receiptType/invoiceGoods.uniqueCode)，前端在向导内部态拿到、我未定位其独立API（OCR返回的那条 receipt 本身 receiptOID=null，故其来源=向导内某步）。定位此"OCR→收据池"富化端点即可全链打通。
- 向导UI: 发票生成费用→upload→OCR→"分别生成费用"(group/auto)→**"推荐/历史选择"选费用类别**→按发票逐张"保存N/5"→存单。类别选择是"生成费用"落行的必需动作。

## 报销单绑定发票结构（已读实体，用于落行）
- 已付个人报销单(ERxxxxx) 读出：5张 `expenseReportInvoices`，每项 `{expenseReportInvoiceOID, expenseReportOID, invoiceOID, invoiceView, status}`，`invoiceView` 含 `expenseTypeId/expenseTypeName`(该票类别，如 其他招待费用/里程补贴)、entityType=INVOICE。
- 报告全部表头键(120+)见 full_3108.json。费用明细行本体在**单独 detail/bag 接口**(v3/详情不返回行)，尚未解锁。
- 已识别真发票→报告绑定所需 invoiceOID 生成依赖收据池富化(见上 gap)。
- 报销模板：`/api/report/template/by/invoice`、`/api/report/template/custom/forms`

## 参与人/代理人查询
- 参与者搜索：`/api/expense/report/participant/search`

## 单据表单 ID（示例用户租户，实测）
- 差旅申请单：formOID=`OID_2`，businessTypeId=181，formType=2001
- 用餐申请单：formOID=`OID_3`
- 差旅报销单：formOID=`OID_4`，businessTypeId=976，formType=3001
- 个人报销单：formOID=`OID_5`
- 对公付款单：formOID=`OID_6`
- 可用表单：`GET /api/custom/forms/my/available?roleType=TENANT&formType=102`(报销单) 或 `formType=101`(申请单)

## 建单验证结果
- `/api/travel/applications/draft` 空 body → 400 "您当前无权限操作此单据"（需在 payload/参数指定单据）
- `/api/expense/reports/custom/form/draft` 空 body → 400 "申请人无单据null的创建权限"（**必须传 formOID/单据**）
- 下一步：拿到表单字段定义（建 dragon ft payload schema），再填值建草稿。

## 下一步
1. 用浏览器建测试草稿，抓 `/api/travel/applications/draft` 与 `/api/expense/reports/custom/form/draft` 的真实 payload（字段结构）。
2. 抓发票上传 multipart 的真实请求格式。
3. 用纯 API 复现：上传发票→OCR→建申请单草稿→建报销单草稿→绑定发票→关联差旅申请单。

# 发票行操作：删除 / 换类别 / 纯 API 落账闭环（2026-08-21 实测）

配合 `list-invoice-line-v5.md` 阅读。核心：**建行落账 = `POST /invoice/api/v5/invoices`**，只要 receipt 带稳定收据池 `id`，纯 API 就能任意落账/删除/重加/换类别。

## 删除发票（实测，参数是 invoiceOID 不是 ERI）
- `DELETE /api/expense/reports/delete/invoice/{expenseReportOID}/{invoiceOID}` → 200，发票从报告移除。
- **参数是 invoiceOID**（如 `676cbf16-…`）；用 expenseReportInvoiceOID(ERI) 会 `404 OBJECT_NOT_FOUND`。
- 软删 `DELETE /api/expense/reports/remove/invoice/{R}/{ERI}` 返回 200 但**不真删**；硬删 `delete/invoice` 才生效（实测软删后绑定仍 3 张）。
- 删除前 `GET /api/expense/report/delete/check/invoice?expenseReportOID=<oid>` → 提示 BACK_BOOK(可账本导入) / DELETE_ALL(不可恢复)。
- 批量：`POST …/delete/invoice/batch/{oid}`。
- **删除后防重解除**：同一发票可再 `v5/invoices` 重加（产生新 invoiceOID）。

## 类别切换（实测）
发票落在哪类 = `v5/invoices` 请求体 `expenseTypeId` / `expenseTypeOID` / `expenseTypeName` 三字段，改这三字段即换类别。
实测：水果票（常熟·51.5，receipt id=2090769160341794817）先删（餐费）→ v5 重加（expenseType=其他招待费用）→ **200 success + 新 invoiceOID 4a9254ca**。

## 重复上传（防重）
对已绑定发票再 `v5/invoices` → `400` 业务校验 `E_DUP_INVOICES_RECEIPTS_AMOUNT_01`「发票可报销总额不足，费用金额超出X」= 服务端防重复。删除后可重加。

## 纯 API 落账闭环（已端到端跑通）
upload → OCR → verify(拿富化 invoiceInfo，含数字 id) → apportionment → tax/amount → **v5/invoices** → 报告自动刷新。步骤与坑见 `list-invoice-line-v5.md`。

## 唯一外部真值（未解）
v5 的 receiptList 里那张票需要**稳定收据池数字 `id`**（如 2090769160341794817）。它由**真人流程首次"发票生成费用"处理该票**时创建；纯 API 独立 OCR→verify 拿到 `R_0000`/receiptOID/beginTime 但 **id 恒 null**。→ 纯 API 落账对新票仍需先由真人在浏览器处理一次拿 id；已有 id 的票（HAR 里存档的）可纯 API 任意操作。

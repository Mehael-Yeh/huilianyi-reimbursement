# 发票上传（方案甲，已验证 200）+ OCR 决策

## ✅ 发票上传纯 API 已验证（2026-08-20，HTTP 200）
**端点**：`POST https://api-a2.huilianyi.com/api/upload/attachment`
**格式**：multipart/form-data，两个字段：
- `attachmentType` = `INVOICE_IMAGES`（发票）
- `file` = `<发票文件>`（PDF/图片均可；实测 PDF 成功）

**返回**：`attachmentOID`(如 `f2c6e4bd-…`) + `id` + `fileURL`(OSS 签名链接) + `fileName`/`fileType`/`thumbnailUrl` 等。

备选：`/api/upload/attachment/v2` 也返回 200（结构略简，含 downloadUrl）。

**此前 500 的根因**：multipart 漏了 `attachmentType` 字段。前端 `createFormData`：`t.append("attachmentType","INVOICE_IMAGES"); t.append("file",e)`（启用加密时再 `append("needEncrypt",true)`）。

**分片上传（大文件）**：`POST /api/v1/upload/attachment/multiple/init` → `/multiple/single?<params>`（FormData = data 逐键 append）→ `/multiple/finish`。

## OCR 决策（用户认可方向：通常跳过）
- 汇联易网页流程是 上传发票→OCR 自动识别金额/日期/商家→生成费用明细行→绑定。
- **但本项目可跳过 OCR**：分类引擎(Invoice-Set `--scan`)已给每张票的类别+金额；测试/模拟票 OCR 不出内容。
- **推荐**：按分类结果直接**手录费用明细行**（类别+金额），发票仅作**附件上传绑定**。只有真实发票图片才值得走 OCR 自动识别管线。
- OCR 端点（未验证命中）：`/api/v1/document/ocr/invoice/scan`(实测404)、`/api/v1/document/ocr/max/invoice/scan`、`/api/llm/ocr/*`、`/api/v1/ocr/template/*`。
- 绑定端点（待实测）：`/api/v1/img/business/attachment/invoice/bind`、`/simple/bind`、`/bind`、`/api/expense/report/invoices/import`。

## 测试资产
- 测试发票：`/vol1/@appdata/trim.hermes/workspace/Invoice-Set/tests/fixtures/`（8 张覆盖 酒店/里程/交通/餐费/停车/礼品/过路费）。
- 上传脚本：`tests/hly_upload_test.py`（multipart `attachmentType=INVOICE_IMAGES + file`）。

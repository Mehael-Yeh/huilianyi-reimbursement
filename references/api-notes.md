# 汇联易登录/鉴权逆向结果（方案甲 · 已打通 ✅）

## ✅ 结论：纯 API 登录已跑通（2026-08-20 实测 HTTP 200 拿到 token）
不依赖浏览器。RSA 加密密码 → OAuth2 密码模式 → Bearer token → 调 API。

## 登录完整配方（Python/curl 可复现）
1. **密码加密**：RSA-2048 PKCS#1 v1.5 加密密码，base64 输出（实测长度 344）。
   - 公钥（硬编码于前端 JS `helios72eb628932.app.js`）：
   ```
   MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0fWgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5NqgxzVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB
   ```
   - 用 `pycryptodome`：`Crypto.Cipher.PKCS1_v1_5` + `RSA.import_key(b64decode(key))`
2. **请求 token**：
   ```
   POST https://console-a2.huilianyi.com/proxy/oauth/token/v2
       ?hlyRequestID=<随机>&client_id=ArtemisWeb&referUrl=https%3A%2F%2Fconsole-a2.huilianyi.com%2F
   Content-Type: application/x-www-form-urlencoded
   body: scope=read write&username=138xxxxxxxx&cryptType=4.0&password=<rsa_b64>&x-helios-client=web&loginType=PcWeb&grant_type=password
   ```
3. **响应**：
   ```json
   [{"access_token":"<uuid>","token_type":"bearer","refresh_token":"<uuid>",
     "expires_in":~96161,"scope":"read write","realm_id":"REALM_ID",
     "realm_base_service_url":"https://api-a2.huilianyi.com",
     "web_entry_url":"https://console-a2.huilianyi.com"}]
   ```

## 调用 API
- 请求头：`Authorization: Bearer <access_token>`
- API 域名：`https://api-a2.huilianyi.com`（realm_base_service_url）
- 也可用 `https://console-a2.huilianyi.com/<path>`（反代同域）
- token 有效期约 27 小时；可用 `refresh_token` 走 `grant_type=refresh_token` 续期（`/oauth/token`）

## 关键常量（示例用户账号）
- username=138xxxxxxxx；tenantId=TENANT_ID；userId=USER_ID
- userOID=OID_1；companyOID=OID_2
- realm_id=REALM_ID；client_id=ArtemisWeb
- 敏感写操作可能另需 `authorizationCode`：`GET /api/auth/code/current/user` → `{"authorizationCode":"xxx"}`

## 已发现的业务 API
- 报销单列表搜索：`POST /api/expense/reports/search/my?roleType=TENANT&page=0&size=20`
- 报销单列表：`GET /api/tableview/list?tableName=expense-report`
- 申请单可用表单：`GET /api/custom/forms/my/available?formType=102`
- 表单定义：`GET /api/custom/forms/by/form/code?formCode=user_attach_form`

## 可复现脚本
- `/vol1/@appdata/trim.hermes/workspace/Invoice-Set/tests/hly_login_test.py`（登录已通）

## 下一步（方案甲待办）
1. 验证 token 调业务 API（search/my、account）。
2. 逆向建差旅申请单/报销单的端点与 payload。
3. 逆向发票上传端点与格式。
4. 若上传纯 API 难 → 退回方案乙。

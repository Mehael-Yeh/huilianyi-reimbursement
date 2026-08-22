# 登录与鉴权

## 流程

1. RSA-2048 PKCS#1 v1.5 加密密码。
2. `POST https://console-a2.huilianyi.com/proxy/oauth/token/v2`
3. OAuth password grant 参数必须包含：
   - `client_id=ArtemisWeb`
   - `x-helios-client=web`
   - `loginType=PcWeb`
   - `cryptType=4.0`
   - `grant_type=password`
4. 业务 API 使用 `Authorization: Bearer <access_token>`。

实现见 `scripts/hly_api.py`。

## 凭据规则

- 初次使用交互询问账号和密码，并在验证成功后保存。
- 账号写入本地配置；密码只写入操作系统凭据库。
- 后续可用可选的 `--username` 切换账号，此时会安全提示该账号的密码并更新本地凭据。
- 不打印凭据，不把密码写入普通文件，也不让凭据进入状态 JSON。
- 仓库中不得出现真实账号密码。

## 为什么不用普通网页登录

网页登录入口可能进入不同部署域。API OAuth 会返回当前账号对应的 `realm_base_service_url`；本 Skill 明确禁止手动或自动化操作浏览器。

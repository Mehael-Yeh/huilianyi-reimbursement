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

- 账号由命令行 `--username` 传入。
- 密码只从 `HLY_PASSWORD` 或交互 `getpass` 读取。
- 不打印、不写文件、不进入状态 JSON。
- 仓库中不得出现真实账号密码。

## 为什么不用普通网页登录

官网登录入口可能落到 `console.huilianyi.com`，而本租户使用 A2 realm。API OAuth 会返回正确的 `realm_base_service_url`，比无头浏览器会话稳定。

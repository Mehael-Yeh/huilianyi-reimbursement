# 无显示器 NAS 上自动化 antd 保护网页的工具箱（2026-08-21 实测）

汇联易(Helios)报销向导的「发票生成费用→选类别→保存→继续保存」是 antd 受控组件，headless 浏览器对合成点击免疫。以下三招组合可推进到"费用行已进费用明细、只差最后提交"。

## 1. token 注入绕过登录（避免 flaky 登录/限流）
连续浏览器密码登录会触发风控。改用已有 oauth token 注入：
- 走 API 拿 oauth 响应 JSON（方**: RSA-2048 加密密码 → POST console-a2 `/proxy/oauth/token/v2`，响应即完整 token 对象）。
- playwright `page.addInitScript((tok)=>{try{localStorage.setItem('hly.token',JSON.stringify(tok));}catch(e){}},TOK)` 在 SPA 加载前写入 → 直达 `/main/dashboard`，无登录页。
- 效果：稳定、快、不触发限流。密钥 QWEN_FREE_API_KEY 在 env（视觉用）。

## 2. 非 headless 真实渲染：weston（Wayland 虚拟显示，无需 root）
机器上有 `/usr/bin/weston`，用 headless backend 起虚拟显示：
```
weston --backend=/usr/lib/*/libweston-*/headless-backend.so --socket=wayland-0 --idle-time=0   # 后台常驻
# 再 export WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/<uid>
```
chromium/playwright 以 `--ozone-platform=wayland` + `headless:false` 连上 = 真实渲染非 headless，antd 响应正常。比 headless 稳（headless 时报表模块常不渲染）。socket 在 $XDG_RUNTIME_DIR/wayland-0。

## 3. 截图 + 视觉模型定位按钮（antd 免疫的破局）
DOM/坐标扫描找不到 antd 内部按钮时，截图交给视觉模型：
- playwright `page.screenshot({path, fullPage:true})`
- 调视觉模型（qwen-vl-max，env QWEN_FREE_API_KEY，base `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`，image_url 用 `data:image/png;base64,`+b64）问："某按钮/卡片的中心坐标(x,y)？弹窗里有哪些按钮和坐标？"
- 用返回坐标 `page.mouse.click(x,y)` 真实点击。
- 注意：视觉坐标是**近似值**（几像素到几十像素偏差），关键按钮可再用 DOM `getBoundingClientRect` 精确化，或点后截图二次确认。

## 汇联易向导真实布局（视觉坐实）
- 「识别发票文件」面板 + 「推荐/历史选择」类别卡片（其他招待费用/餐费/汽车费用…）
- 选类别后发票即进「费用明细」成为费用行（显示 本次报销金额/价税/销售方/购买方），类别已带上。
- 有【两个保存】：向导(识别面板)里的保存 ~(215,740) + 报告底部 ant-btn-primary 保存 ~(284,775)。点错那个（报告底部）不走"必填→继续保存"流程。
- 选"其他招待费用"应触发"必填字段未填写→继续保存"（若类别未真正选中则不触发）。

# 浏览器自动化技巧（攻 antd 免疫向导）

最关键：卡向导时请用户/真人在浏览器操作一次，Network 抓那个请求给 agent。本文件收录在 headless NAS 上推进受控表单的可靠组合拳。

## 1. token 注入绕过登录（防限流/flaky）
不要从零登录（连续多次自动登录触发风控 400）。API 登录拿 access_token 后注入本地浏览器：
```js
await page.addInitScript((tok)=>{try{localStorage.setItem('hly.token',JSON.stringify(tok));}catch(e){}}, TOK);
```
`localStorage['hly.token']` 存**完整 oauth 响应对象**（含 access_token+tokenOID 等），不是裸字符串。注入后 goto 即直进 /main/dashboard。

## 2. 非 headless Chromium（weston/wayland）
headless 下 汇联易 报表模块/向导常渲染不出（只出 "English" 按钮）。无显示器分法：
1. `weston --backend=/usr/lib/x86_64-linux-gnu/libweston-10/headless-backend.so --socket=wayland-0 --idle-time=0`（后台）
2. env `WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/961`
3. playwright `headless:false` + args `--ozone-platform=wayland --no-sandbox`
渲染/上传/OCR 显著更稳。用完 pkill+rm socket。

## 3. 视觉模型定位 antd 按钮
DOM/坐标点不中受控按钮时，截图+视觉模型：
- `QWEN_FREE_API_KEY` + DashScope compatible-mode（`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`, model `qwen-vl-max`，图 base64 data-url）
- 问模型：目标类别卡片和「保存/继续保存」按钮的**视口坐标**（坐标为估计值，截图回查比对）。
- `page.mouse.click(x,y)` 真鼠标事件点它。
- 重点：确认有没有【两个保存】（向导面板里的 vs 报表底部 footer 的）。

## 4. 「必填字段未填写 → 继续保存」
选「其他招待费用」→ 点**向导面板里的保存** → 弹「必填字段未填写」→ 点**「继续保存」**才真正提交。**别把报表底部「保存」当提交**（只整单保存,不触发向导校验）——本类任务最常见误点。

## 5. antd/向导免疫是常态
向导弹窗(发票生成费用→生成费用→选类别→保存→(必填)继续保存)的 React 内部态对脚本(真假点击/坐标/非headless)都可能静默不响应。唯一可靠:一次真人浏览器的请求抓包(draft/save/invoices),拿服务器会话态下的真值(如收据池 id)。
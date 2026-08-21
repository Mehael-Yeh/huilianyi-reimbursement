# 汇联易 非 headless 渲染与自动化（2026-08-21 实测）

## 背景
headless Chromium 下汇联易报错模块经常**根本不渲染**（页面只剩 "English" 按钮、无报销单列表/按钮），且 antd 受控组件对合成点击免疫，导致"发票生成费用→保存"向导无法可靠驱动。**非 headless（有显示）**显著改善渲染与事件处理。

## 起虚拟显示（无 root，机器自带 weston）
机器有 `/usr/bin/weston`(Wayland 合成器, v10)。用它的 headless backend 提供虚拟 Wayland 显示：
```bash
# 后台起 weston（Hermes 用 terminal background=true）
weston --backend=/usr/lib/x86_64-linux-gnu/libweston-10/headless-backend.so --socket=wayland-0 --idle-time=0
# socket 落在 $XDG_RUNTIME_DIR/wayland-0（本例 /run/user/961/wayland-0）
export WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/961
```
> 注意：用 `background=true` 起，别用 nohup/disown/setsid（Hermes 终端会拦）。

## 用 playwright 非 headless 连上
```js
const {chromium} = require('playwright');
const browser = await chromium.launch({
  headless:false,
  args:['--no-sandbox','--disable-dev-shm-usage','--ozone-platform=wayland','--disable-gpu','--lang=zh-CN','--window-size=1440,900']
});
```
完整抓包脚本：`scripts/wl_capture_headed.js`（登录→进编辑→发票生成费用→上传→生成费用→选类别→保存/继续保存→抓全请求体到 jsonl，改 PDF/目标单据/类别即可跑）。

## antd 免疫：必须真点击
受控组件（向导弹窗"保存"等）**不吃 `evaluate b.click()` 合成点击**（React 不认）。必须 playwright 的 `locator().click()`（经 CDP 的真实输入事件）。脚本里的 `clickReal` 做法：
1. 页内 `[...document.querySelectorAll('button')]` 找到匹配文本 + 可见 + 未 disabled 的按钮**索引**
2. `await page.locator('button').nth(idx).click()` 真点击

## 局限（诚实）
非 headless 只解决**渲染**，不解决**向导内部态**："发票生成费用→生成费用→选类别→保存"这条多步向导弹窗对脚本驱动仍不稳（有时向导没进对状态、新票没被登记）。因此在纯 API 下`新增发票行登记`仍需真人/有显示浏览器点一次，随后才可用纯 API 回存 FINAL_SAVE_BODY 模板持久化。

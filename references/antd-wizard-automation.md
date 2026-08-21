# 汇联易发票生成费用向导：自动化边界（2026-08-21 实测）

## 向导必经流程（用户亲授，真值）
识别 → 选「其他招待费用」→ **必现「必填字段未填写」弹窗** → 点「**继续保存**」→ 发票行才真正登记落账。
- 若选了「其他招待费用」后**没有出现**必填弹窗，说明类别的 antd 选择块**没被自动化真正点进**（常见：只点了文本节点/DOM，没触发 React onSelect）——这是"类别没注册 → 弹窗不出现 → 保存空转"的根因诊断点。

## 向导提交按钮 = 不可靠自动化点
- 发票生成费用向导的「保存 / 生成费用」是 **antd 受控组件**。
- 下列方式都常点不中 / 点了无网络请求（实测）：DOM `el.click()`、playwright `.click()`、`page.mouse.click(x,y)` 坐标点击、（headless 与非 headless / weston-wayland 皆然）。
- 表现：类别选了没真正注册、必填弹窗不出现、把「整单保存」（报告底部 ant-btn-primary）当成向导保存点空转、甚至点完整单保存返回列表。

## 推荐替代：截图 + 视觉模型定位（用户建议，方向正确）
- 别死磕 DOM/坐标解析来定位 antd 向导按钮；改 **`page.screenshot()` 截图 → 视觉模型（qwen-vl 类）读图给出按钮像素坐标 → `page.mouse.click(x,y)`**。
- 截图脚本范式见 `scripts/wl_capture_headed.js`（非headless/weston 通道，见 `references/non-headless-rendering.md`）。

## 相关边界结论
- 新增发票行落账：识别/分类/建单单纯 API 全通；但把**新**发票行持久化要靠系统向导内部注册（见 `references/api-endpoints.md`「落账最终定论」），纯 API 手拼 invoiceView 会被服务端发票记录校验 400 拒。最可靠收口 = 真人浏览器一次向导保存请求做逐字段对照。

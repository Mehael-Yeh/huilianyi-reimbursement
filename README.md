# 汇联易报销 Skill

让 Codex Agent 根据用户上传的 PDF、OFD、ZIP、XML 票据，协助创建汇联易差旅申请、差旅报销和个人报销草稿，并交付 Excel 分类金额核对表。

## 安装

在 PowerShell 中克隆到 Codex Skills 目录并安装依赖：

```powershell
git clone https://github.com/Mehael-Yeh/huilianyi-reimbursement.git "$HOME\.codex\skills\huilianyi-reimbursement"
python -m pip install -r "$HOME\.codex\skills\huilianyi-reimbursement\requirements.txt"
```

私有仓库需要先使用有权访问该仓库的 GitHub 账号完成 Git 认证。更新 Skill：

```powershell
git -C "$HOME\.codex\skills\huilianyi-reimbursement" pull --ff-only
```

## 使用

在 Codex 中上传票据，然后直接说明要创建差旅申请、差旅报销或个人报销。Agent 会读取本 Skill，询问缺少的账号、单据关联、人员、日期及费用信息，并在执行汇联易草稿写入前确认。

支持 PDF、OFD、ZIP、XML；图片票据不会上传。ZIP 加密时，Agent 会向用户索取密码，密码不会写入仓库。

本 Skill 只创建或编辑草稿，不提交、删除、关闭或撤回单据。Agent 的完整工作流见 [SKILL.md](SKILL.md)。

## 许可证

[MIT License](LICENSE)

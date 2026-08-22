# 汇联易报销 Skill

让 Agent 根据用户上传的 PDF、OFD、ZIP、XML 票据，协助创建汇联易差旅申请、差旅报销和个人报销草稿，并交付 Excel 分类金额核对表。

## 安装

克隆仓库并安装 Python 依赖：

```bash
git clone https://github.com/Mehael-Yeh/huilianyi-reimbursement.git
python -m pip install -r huilianyi-reimbursement/requirements.txt
```

将整个 `huilianyi-reimbursement` 目录添加到所用 Agent 的 Skill 搜索路径；具体导入方式和目录位置以该 Agent 的文档为准。私有仓库需要先使用有权访问该仓库的 GitHub 账号完成认证。

## 使用

向 Agent 上传票据，然后说明要创建差旅申请、差旅报销或个人报销。Agent 会读取本 Skill，补充询问缺少的信息，并在写入汇联易草稿前确认。

支持 PDF、OFD、ZIP、XML；图片票据不会上传。ZIP 加密时，Agent 会向用户索取密码，密码不会写入仓库。

本 Skill 只创建或编辑草稿，不提交、删除、关闭或撤回单据。Agent 的完整工作流见 [SKILL.md](SKILL.md)。

## 许可证

[MIT License](LICENSE)

# 汇联易报销 Skill

让 Agent 根据用户上传的 PDF、OFD、ZIP、XML 票据，协助创建汇联易差旅申请、差旅报销和个人报销草稿，并交付 Excel 分类金额核对表。

## 快速安装：复制给你的 Agent

复制下面整段内容，直接发送给你正在使用的 Agent：

```text
请把 https://github.com/Mehael-Yeh/huilianyi-reimbursement 安装或更新为可调用的 Skill，名称为 huilianyi-reimbursement。

优先使用你自带的 Skill 安装机制；如果没有，请把仓库克隆到你的用户级 Skill 目录，并安装 requirements.txt 中的 Python 依赖。

安装后请完整读取 SKILL.md，运行可用的 Skill 结构校验和项目测试，并确认该 Skill 能被发现。只向我报告安装路径、当前提交或版本、校验结果；本次不要登录汇联易，也不要创建任何申请单或报销单。
```

## 手动安装

克隆仓库并安装 Python 依赖：

```bash
git clone https://github.com/Mehael-Yeh/huilianyi-reimbursement.git
python -m pip install -r huilianyi-reimbursement/requirements.txt
```

将整个 `huilianyi-reimbursement` 目录添加到所用 Agent 的 Skill 搜索路径；具体导入方式和目录位置以该 Agent 的文档为准。私有仓库需要先使用有权访问该仓库的 GitHub 账号完成认证。

## 使用

向 Agent 上传票据，然后说明要创建差旅申请、差旅报销或个人报销。Agent 会读取本 Skill，补充询问缺少的信息，并在写入汇联易草稿前确认。

首次使用会同时询问汇联易账号和密码：账号保存在本地配置中，密码保存在操作系统凭据库中。材料分类完成后，Agent 会主动询问本次报销的开始和结束日期。正常提报按费用类别批量处理，一类票据形成一条含多张票据的费用行；最后必须回读核验并生成 Excel 报销清单。

支持 PDF、OFD、ZIP、XML；图片票据不会上传。ZIP 加密时，Agent 会向用户索取密码，密码不会写入仓库。

本 Skill 全程使用汇联易 API，不操作浏览器；只创建或编辑草稿，不提交、删除、关闭或撤回单据。Agent 的完整工作流见 [SKILL.md](SKILL.md)。

## 许可证

[MIT License](LICENSE)

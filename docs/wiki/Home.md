# 汇联易报销填报 Wiki

本项目通过汇联易 A2 API 辅助完成票据分类、申请和报销草稿、费用保存、回读验收及 Excel 核对表交付。

## 从这里开始

- [安装与首次运行](Getting-Started.md)
- [工作流与安全边界](Workflow-and-Safety.md)
- [票据识别与分类](Invoice-Recognition.md)
- [命令行参考](CLI-Reference.md)
- [Excel 核对表](Review-Workbook.md)
- [故障排查](Troubleshooting.md)

## 不会执行的操作

自动化不会提交、删除、关闭或撤回申请单、报销单和费用。所有写入命令只处理编辑中草稿，并要求显式确认参数。

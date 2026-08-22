# 命令行参考

## 只读命令

```bash
python scripts/hly.py profile --username <账号> --output tmp/profile.json
python scripts/hly.py history --username <账号> --output tmp/history.json
python scripts/hly.py verify-report --username <账号> --report <报销单号>
python scripts/hly.py audit-travel-pair --username <账号> --application <申请单号> --report <报销单号>
```

## 草稿与费用

```bash
python scripts/hly.py create-application <参数> --confirm-draft-write
python scripts/hly.py create-reports <参数> --confirm-draft-write
python scripts/hly.py add-invoice <参数> --confirm-draft-write
python scripts/hly.py add-manual-expense <参数> --confirm-draft-write
```

查看每个子命令的完整参数：

```bash
python scripts/hly.py <子命令> --help
```

## 票据预检与核对表

```bash
python scripts/invoice_extract.py <文件...> --output tmp/invoice-review.json
python scripts/hly.py prepare-review --username <账号> \
  --report <报销单号> --invoice-review tmp/invoice-review.json \
  --output tmp/reimbursement-review.json
node scripts/build_review_workbook.mjs \
  tmp/reimbursement-review.json outputs/报销分类金额核对.xlsx
```

差旅和个人报销同时存在时，可重复传入 `--report`。

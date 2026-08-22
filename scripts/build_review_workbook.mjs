#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: build_review_workbook.mjs <review.json> <output.xlsx>");
}
const data = JSON.parse(await fs.readFile(inputPath, "utf8"));
const rows = data.rows || [];
const categories = data.categories || [];
const metadata = data.metadata || {};
const excelTextFormula = (value) => `="${String(value).replaceAll('"', '""')}"`;
const workbook = Workbook.create();
const summary = workbook.worksheets.add("汇总");
const details = workbook.worksheets.add("票据明细");
const categorySheet = workbook.worksheets.add("类别核对");
workbook.comments.setSelf({ displayName: "Mehael Yeh" });

for (const sheet of [summary, details, categorySheet]) {
  sheet.showGridLines = false;
}

const titleStyle = { fill: "#17365D", font: { bold: true, color: "#FFFFFF", size: 16 } };
const headerStyle = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" }, borders: { preset: "outside", style: "thin", color: "#9EADBA" } };
const currencyFormat = "#,##0.00";

summary.getRange("A1:F1").merge();
summary.getRange("A1").values = [["报销分类与金额核对"]];
summary.getRange("A1:F1").format = titleStyle;
summary.getRange("A3:B7").values = [
  ["报销单", (metadata.reportCodes || []).filter(Boolean).join("，")],
  ["汇联易回读总额", Number(metadata.reportTotal || 0)],
  ["明细最终金额", null],
  ["待确认数量", null],
  ["保存失败数量", Number(metadata.failedExpenses || 0)],
];
summary.getRange("A3:A7").format = headerStyle;
const detailEnd = Math.max(rows.length + 2, 3);
summary.getRange("B5").formulas = [[`=SUM('票据明细'!I3:I${detailEnd})`]];
summary.getRange("B6").formulas = [[`=COUNTIF('票据明细'!M3:M${detailEnd},"是")`]];
summary.getRange("B4:B5").format.numberFormat = currencyFormat;
summary.getRange("A9:E9").values = [["类别", "申请金额", "报销金额", "差额", "票据数量"]];
summary.getRange("A9:E9").format = headerStyle;
const categoryNames = [...new Set([
  ...categories.map((item) => item.expenseType),
  ...rows.map((item) => item.confirmedCategory || item.suggestedCategory),
].filter(Boolean))];
if (categoryNames.length) {
  summary.getRange(`A10:A${9 + categoryNames.length}`).values = categoryNames.map((value) => [value]);
  for (let index = 0; index < categoryNames.length; index += 1) {
    const row = 10 + index;
    const source = categories.find((item) => item.expenseType === categoryNames[index]);
    summary.getRange(`B${row}`).values = [[Number(source?.applicationAmount || 0)]];
    summary.getRange(`C${row}`).formulas = [[`=SUMIF('票据明细'!F$3:F$${detailEnd},A${row},'票据明细'!I$3:I$${detailEnd})`]];
    summary.getRange(`D${row}`).formulas = [[`=C${row}-B${row}`]];
    summary.getRange(`E${row}`).formulas = [[`=COUNTIF('票据明细'!F$3:F$${detailEnd},A${row})`]];
  }
  summary.getRange(`B10:D${9 + categoryNames.length}`).format.numberFormat = currencyFormat;
}
summary.getRange("A:F").format.columnWidth = 18;
summary.getRange("A:A").format.columnWidth = 24;

const headers = [
  "文件名", "格式", "材料类型", "发票号码", "自动建议分类", "用户确认分类", "归属单据",
  "识别金额", "最终报销金额", "金额来源", "分类依据", "置信度", "是否需核对",
  "汇联易费用编号", "保存状态", "报销单号", "备注",
];
details.getRange("A1:Q1").merge();
details.getRange("A1").values = [["票据明细"]];
details.getRange("A1:Q1").format = titleStyle;
details.getRange("A2:Q2").values = [headers];
details.getRange("A2:Q2").format = headerStyle;
details.getRange(`D3:D${detailEnd}`).format.numberFormat = "@";
details.getRange(`N3:P${detailEnd}`).format.numberFormat = "@";
if (rows.length) {
  details.getRange(`A3:Q${rows.length + 2}`).values = rows.map((item) => [
    item.fileName || "", item.format || "", item.documentType || "", "",
    item.suggestedCategory || "", item.confirmedCategory || "", item.reportGroup || "",
    item.recognizedAmount ?? null, item.finalAmount ?? null, item.amountSource || "",
    item.classificationBasis || "", item.confidence || "", item.needsReview || "",
    item.expenseCode || "", item.saveStatus || "", item.reportCode || "", item.notes || "",
  ]);
  details.getRange(`H3:I${rows.length + 2}`).format.numberFormat = currencyFormat;
  rows.forEach((item, index) => {
    if (item.invoiceNumber) details.getRange(`D${index + 3}`).formulas = [[excelTextFormula(item.invoiceNumber)]];
  });
  details.getRange(`M3:M${rows.length + 2}`).conditionalFormats.add("containsText", { text: "是", format: { fill: "#FFF2CC", font: { color: "#9C6500", bold: true } } });
  details.getRange(`O3:O${rows.length + 2}`).conditionalFormats.add("containsText", { text: "失败", format: { fill: "#FCE4D6", font: { color: "#C00000", bold: true } } });
  details.getRange(`F3:F${rows.length + 2}`).dataValidation = { rule: { type: "list", values: categoryNames.length ? categoryNames : ["待确认"] } };
  details.tables.add(`A2:Q${rows.length + 2}`, true, "InvoiceReviewTable");
}
details.freezePanes.freezeRows(2);
details.getRange("A:Q").format.columnWidth = 14;
details.getRange("A:A").format.columnWidth = 34;
details.getRange("D:D").format.columnWidth = 24;
details.getRange("J:K").format.columnWidth = 24;
details.getRange("Q:Q").format.columnWidth = 28;
details.getRange(`A2:Q${detailEnd}`).format.wrapText = true;

categorySheet.getRange("A1:F1").merge();
categorySheet.getRange("A1").values = [["类别核对"]];
categorySheet.getRange("A1:F1").format = titleStyle;
categorySheet.getRange("A2:F2").values = [["类别", "申请金额", "报销金额", "差额", "票据数量", "未匹配数量"]];
categorySheet.getRange("A2:F2").format = headerStyle;
if (categoryNames.length) {
  categorySheet.getRange(`A3:A${categoryNames.length + 2}`).values = categoryNames.map((value) => [value]);
  for (let index = 0; index < categoryNames.length; index += 1) {
    const row = 3 + index;
    const source = categories.find((item) => item.expenseType === categoryNames[index]);
    categorySheet.getRange(`B${row}`).values = [[Number(source?.applicationAmount || 0)]];
    categorySheet.getRange(`C${row}`).formulas = [[`=SUMIF('票据明细'!F$3:F$${detailEnd},A${row},'票据明细'!I$3:I$${detailEnd})`]];
    categorySheet.getRange(`D${row}`).formulas = [[`=C${row}-B${row}`]];
    categorySheet.getRange(`E${row}`).formulas = [[`=COUNTIF('票据明细'!F$3:F$${detailEnd},A${row})`]];
    categorySheet.getRange(`F${row}`).formulas = [[`=COUNTIFS('票据明细'!F$3:F$${detailEnd},A${row},'票据明细'!O$3:O$${detailEnd},"未匹配")`]];
  }
  categorySheet.getRange(`B3:D${categoryNames.length + 2}`).format.numberFormat = currencyFormat;
}
categorySheet.freezePanes.freezeRows(2);
categorySheet.getRange("A:F").format.columnWidth = 18;

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const previewDir = path.join(path.dirname(outputPath), ".previews");
await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["汇总", "票据明细", "类别核对"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const inspection = await workbook.inspect({ kind: "table", range: `票据明细!A1:Q${detailEnd}`, include: "values,formulas", tableMaxRows: 12, tableMaxCols: 17 });
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ output: path.resolve(outputPath), inspection: inspection.ndjson, errors: errors.ndjson }, null, 2));

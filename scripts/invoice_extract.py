#!/usr/bin/env python3
"""Extract text, amount and reimbursement category from supported invoice files."""

from __future__ import annotations

import argparse
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SUPPORTED_SUFFIXES = {".pdf", ".ofd", ".zip", ".xml"}
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024

STRONG_KEYWORDS = {
    "过路费": ("收费公路通行费", "道路通行服务", "高速公路通行费", "ETC通行费", "过路费", "过桥费", "过闸费"),
    "酒店": ("住宿服务", "住宿费", "客房费", "房费", "宾馆住宿", "酒店服务"),
    "停车费": ("停车服务", "车辆停放服务", "停车费", "停车场服务"),
    "打车费": ("出租车客运服务", "出租汽车", "网约车", "打车服务", "代驾服务", "滴滴出行", "高德打车"),
    "其他交通": ("铁路电子客票", "航空运输电子客票", "航空运输客票", "火车票", "高铁票", "动车票", "机票", "客运票"),
    "餐费": ("餐饮服务", "餐饮费", "餐费"),
    "礼品费": ("礼品", "烟草制品", "茶叶", "酒类", "水果", "焙烤食品", "预包装食品", "超市", "便利店", "百货"),
    "里程补贴": ("油卡充值", "油卡", "加油", "成品油", "车用汽油", "车用柴油", "汽油", "柴油", "燃油费"),
}

WEAK_KEYWORDS = {
    "过路费": ("通行费", "收费公路", "高速通行"),
    "酒店": ("酒店", "宾馆", "旅馆", "住宿"),
    "停车费": ("停车", "车辆停放"),
    "打车费": ("出租车", "网约", "打车", "代驾", "出行服务"),
    "其他交通": ("铁路", "航空", "高铁", "动车", "旅客运输"),
    "餐费": ("餐饮", "饭店", "餐馆", "酒楼", "小吃"),
    "礼品费": ("食品", "饮料", "酒", "茶", "烟", "水果", "商贸"),
    "里程补贴": ("油品", "加油站", "石油", "石化"),
}

SUPPORTING_DOCUMENT_KEYWORDS = (
    "通行费电子票据汇总单", "通行记录", "通行费汇总单", "打车行程单", "出行行程单"
)

AMOUNT_LABELS = (
    ("TotalTaxIncludedAmount", 110),
    ("TaxInclusiveTotalAmount", 110),
    ("AmountIncludingTax", 110),
    ("价税合计（小写）", 100),
    ("价税合计(小写)", 100),
    ("价税合计", 90),
    ("票价合计", 90),
    ("实付金额", 85),
    ("支付金额", 85),
    ("应付金额", 80),
    ("合计金额", 80),
    ("金额合计", 80),
    ("总金额", 75),
)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or ""))


def _xml_text(raw: bytes) -> str:
    root = ElementTree.fromstring(raw)
    values = []
    for element in root.iter():
        if element.text and element.text.strip():
            values.append(element.text.strip())
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name:
            values.append(local_name)
    return "\n".join(values)


def _pdf_text(source: Any) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pypdf") from exc
    return "\n".join((page.extract_text() or "") for page in PdfReader(source).pages)


def _archive_text(raw: bytes, suffix: str) -> str:
    values = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        total = sum(item.file_size for item in archive.infolist())
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive expands beyond the safety limit")
        for item in archive.infolist():
            if item.is_dir():
                continue
            child_suffix = Path(item.filename).suffix.lower()
            if child_suffix in {".pdf", ".xml", ".ofd", ".zip"}:
                child = archive.read(item)
                if child_suffix == ".pdf":
                    values.append(_pdf_text(io.BytesIO(child)))
                elif child_suffix == ".xml":
                    try:
                        values.append(_xml_text(child))
                    except ElementTree.ParseError:
                        values.append(child.decode("utf-8", errors="ignore"))
                else:
                    values.append(_archive_text(child, child_suffix))
    return "\n".join(values)


def extract_text(path: str | Path) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported invoice format: {suffix or '<none>'}")
    if suffix == ".pdf":
        return _pdf_text(str(source))
    raw = source.read_bytes()
    if suffix == ".xml":
        return _xml_text(raw)
    return _archive_text(raw, suffix)


def _money(value: str) -> float | None:
    normalized = value.replace(",", "").replace("￥", "").replace("¥", "").strip()
    if not re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?", normalized):
        return None
    amount = round(float(normalized), 2)
    return amount if 0 < amount < 100_000_000 else None


def extract_amount(text: str, filename: str = "") -> dict[str, Any]:
    normalized = unicodedata.normalize("NFKC", text or "")
    candidates: list[dict[str, Any]] = []
    for label, score in AMOUNT_LABELS:
        pattern = re.compile(
            re.escape(unicodedata.normalize("NFKC", label))
            + r"[^\d￥¥]{0,24}[￥¥]?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(normalized):
            amount = _money(match.group(1))
            if amount is not None:
                candidates.append({"amount": amount, "source": label, "score": score})

    for match in re.finditer(r"[￥¥]\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", normalized):
        context = normalized[max(0, match.start() - 16):match.end() + 4]
        if any(term in context for term in ("税额", "单价", "不含税", "优惠", "折扣")):
            continue
        amount = _money(match.group(1))
        if amount is not None:
            candidates.append({"amount": amount, "source": "货币符号", "score": 50})

    filename_match = re.search(
        r"(?:金额|价税合计|合计)[-_ ]*[￥¥]?([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        unicodedata.normalize("NFKC", filename),
        re.IGNORECASE,
    )
    if filename_match:
        amount = _money(filename_match.group(1))
        if amount is not None:
            candidates.append({"amount": amount, "source": "文件名金额标签", "score": 40})

    if not candidates:
        return {"amount": None, "source": None, "confidence": "low", "needsReview": True, "candidates": []}
    candidates.sort(key=lambda item: (-item["score"], -item["amount"]))
    best = candidates[0]
    same_priority = {item["amount"] for item in candidates if item["score"] == best["score"]}
    conflicts = len(same_priority) > 1
    return {
        "amount": best["amount"],
        "source": best["source"],
        "confidence": "low" if conflicts or best["score"] < 75 else "high",
        "needsReview": conflicts or best["score"] < 75,
        "candidates": candidates,
    }


def extract_invoice_number(text: str) -> str | None:
    normalized = compact_text(text)
    for pattern in (
        r"(?:发票号码|发票号|票据号码)[:：]?([0-9]{8,20})",
        r"(?:InvoiceNumber|InvoiceNo)[:：]?([0-9]{8,20})",
        r"(?<![0-9])([0-9]{20})(?![0-9])",
    ):
        match = re.search(pattern, normalized)
        if match:
            return match.group(1)
    return None


def classify_invoice(text: str, filename: str = "", amount: float | None = None) -> dict[str, Any]:
    haystack = compact_text(f"{text}\n{filename}")
    invoice_number = extract_invoice_number(text)
    support_hits = [term for term in SUPPORTING_DOCUMENT_KEYWORDS if compact_text(term) in haystack]
    if support_hits and not invoice_number:
        return {
            "category": "附件", "reportGroup": "随对应费用", "confidence": "high",
            "needsReview": False, "countAmount": False, "matchedKeywords": support_hits,
        }

    scored = []
    for category in STRONG_KEYWORDS:
        strong = [term for term in STRONG_KEYWORDS[category] if compact_text(term) in haystack]
        weak = [term for term in WEAK_KEYWORDS[category] if compact_text(term) in haystack]
        score = len(strong) * 10 + len(weak) * 3
        if score:
            scored.append((score, category, strong + weak))
    scored.sort(reverse=True)
    if not scored:
        return {
            "category": "待确认", "reportGroup": "待确认", "confidence": "low",
            "needsReview": True, "countAmount": True, "matchedKeywords": [],
        }

    score, category, matched = scored[0]
    conflict = len(scored) > 1 and scored[1][0] == score
    if category == "餐费" and amount is not None and amount > 40:
        category = "礼品费"
        matched.append("餐饮金额>40")
    group = "差旅报销" if category in {"过路费", "酒店", "停车费", "打车费", "其他交通"} else "个人报销"
    return {
        "category": category,
        "reportGroup": group,
        "confidence": "low" if conflict or score < 10 else "high",
        "needsReview": conflict or score < 10 or category == "里程补贴",
        "countAmount": True,
        "matchedKeywords": matched,
    }


def inspect_invoice(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = extract_text(source)
    amount = extract_amount(text, source.name)
    classification = classify_invoice(text, source.name, amount["amount"])
    return {
        "file": str(source.resolve()),
        "fileName": source.name,
        "format": source.suffix.lower().lstrip(".").upper(),
        "invoiceNumber": extract_invoice_number(text),
        **amount,
        **classification,
    }


def inspect_invoices(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() != ".zip":
        return [inspect_invoice(source)]
    rows = []
    raw = source.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        total = sum(item.file_size for item in archive.infolist())
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive expands beyond the safety limit")
        for item in archive.infolist():
            if item.is_dir():
                continue
            suffix = Path(item.filename).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                continue
            child = archive.read(item)
            if suffix == ".pdf":
                text = _pdf_text(io.BytesIO(child))
            elif suffix == ".xml":
                text = _xml_text(child)
            else:
                text = _archive_text(child, suffix)
            display_name = f"{source.name}!{item.filename}"
            amount = extract_amount(text, display_name)
            classification = classify_invoice(text, display_name, amount["amount"])
            rows.append({
                "file": str(source.resolve()), "fileName": display_name,
                "format": suffix.lstrip(".").upper(), "invoiceNumber": extract_invoice_number(text),
                **amount, **classification,
            })
    if not rows:
        raise ValueError("ZIP contains no supported PDF/OFD/XML documents")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect supported invoice documents")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--output")
    args = parser.parse_args()
    rows = [row for path in args.files for row in inspect_invoices(path)]
    value = {"rows": rows}
    output = json.dumps(value, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

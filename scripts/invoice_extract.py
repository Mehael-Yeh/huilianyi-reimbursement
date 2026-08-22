#!/usr/bin/env python3
"""Extract text, amount and reimbursement category from supported invoice files."""

from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SUPPORTED_SUFFIXES = {".pdf", ".ofd", ".zip", ".xml"}
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


class ArchivePasswordRequired(ValueError):
    """Raised when an encrypted ZIP entry cannot be read without a password."""


class ArchivePasswordError(ValueError):
    """Raised when the supplied ZIP password is not accepted."""

STRONG_KEYWORDS = {
    "过路费": ("收费公路通行费", "道路通行服务", "高速公路通行费", "ETC通行费", "通行费", "过路费", "过桥费", "过闸费"),
    "酒店": ("住宿服务", "住宿费", "客房费", "房费", "宾馆住宿", "酒店服务"),
    "停车费": ("停车服务", "车辆停放服务", "停车费", "停车场服务"),
    "打车费": ("出租车客运服务", "出租汽车", "网约车", "打车服务", "代驾服务", "滴滴出行", "高德打车"),
    "其他交通": ("铁路电子客票", "航空运输电子客票", "航空运输客票", "火车票", "高铁票", "动车票", "机票", "客运票"),
    "餐费": ("餐饮服务", "餐饮费", "餐费"),
    "礼品费": ("礼品", "烟草制品", "茶叶", "酒类", "水果", "焙烤食品", "预包装食品", "超市", "便利店", "百货"),
    "里程补贴": ("油卡充值", "油卡", "加油", "成品油", "车用汽油", "车用柴油", "汽油", "柴油", "燃油费"),
}

WEAK_KEYWORDS = {
    "过路费": ("收费公路", "高速通行"),
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
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name:
            values.append(local_name)
        if element.text and element.text.strip():
            values.append(element.text.strip())
    return "\n".join(values)


def _pdf_text(source: Any) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires pypdf") from exc
    return "\n".join((page.extract_text() or "") for page in PdfReader(source).pages)


def _password_bytes(password: str | bytes | None) -> bytes | None:
    if password is None or isinstance(password, bytes):
        return password
    return password.encode("utf-8")


def _open_archive(raw: bytes):
    try:
        import pyzipper
    except ImportError:
        return zipfile.ZipFile(io.BytesIO(raw))
    return pyzipper.AESZipFile(io.BytesIO(raw))


def _read_archive_entry(archive, item, password: str | bytes | None) -> bytes:
    if item.flag_bits & 1 and password is None:
        raise ArchivePasswordRequired("encrypted ZIP requires a password")
    try:
        return archive.read(item, pwd=_password_bytes(password))
    except (RuntimeError, NotImplementedError) as exc:
        message = str(exc).lower()
        if "password" in message or item.flag_bits & 1:
            raise ArchivePasswordError("ZIP password is incorrect or encryption is unsupported") from exc
        raise


def _member_name(item) -> str:
    name = str(item.filename)
    if not item.flag_bits & 0x800:
        try:
            return name.encode("cp437").decode("gbk")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name


def _archive_text(raw: bytes, suffix: str, password: str | bytes | None = None) -> str:
    values = []
    with _open_archive(raw) as archive:
        total = sum(item.file_size for item in archive.infolist())
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive expands beyond the safety limit")
        for item in archive.infolist():
            if item.is_dir():
                continue
            child_suffix = Path(_member_name(item)).suffix.lower()
            if child_suffix in {".pdf", ".xml", ".ofd", ".zip"}:
                child = _read_archive_entry(archive, item, password)
                if child_suffix == ".pdf":
                    values.append(_pdf_text(io.BytesIO(child)))
                elif child_suffix == ".xml":
                    try:
                        values.append(_xml_text(child))
                    except ElementTree.ParseError:
                        values.append(child.decode("utf-8", errors="ignore"))
                else:
                    values.append(_archive_text(child, child_suffix, password))
    return "\n".join(values)


def extract_text(path: str | Path, password: str | bytes | None = None) -> str:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported invoice format: {suffix or '<none>'}")
    if suffix == ".pdf":
        return _pdf_text(str(source))
    raw = source.read_bytes()
    if suffix == ".xml":
        return _xml_text(raw)
    return _archive_text(raw, suffix, password)


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


def inspect_invoice(path: str | Path, password: str | bytes | None = None) -> dict[str, Any]:
    source = Path(path)
    text = extract_text(source, password)
    amount = extract_amount(text, source.name)
    classification = classify_invoice(text, source.name, amount["amount"])
    return _combined_row({
        "file": str(source.resolve()),
        "fileName": source.name,
        "format": source.suffix.lower().lstrip(".").upper(),
        "invoiceNumber": extract_invoice_number(text),
    }, amount, classification)


def _combined_row(
    base: dict[str, Any], amount: dict[str, Any], classification: dict[str, Any]
) -> dict[str, Any]:
    return {
        **base,
        **amount,
        **classification,
        "amountConfidence": amount["confidence"],
        "classificationConfidence": classification["confidence"],
        "amountNeedsReview": amount["needsReview"],
        "classificationNeedsReview": classification["needsReview"],
        "confidence": (
            "high" if amount["confidence"] == classification["confidence"] == "high" else "low"
        ),
        "needsReview": amount["needsReview"] or classification["needsReview"],
    }


def _deduplicate_archive_rows(
    rows: list[dict[str, Any]], preferred_format: str | None = None
) -> list[dict[str, Any]]:
    stem_formats: dict[str, set[str]] = {}
    for row in rows:
        member_name = str(row.get("fileName") or "").split("!", 1)[-1]
        stem = Path(member_name).stem.casefold()
        if stem:
            stem_formats.setdefault(stem, set()).add(str(row.get("format") or ""))
    grouped: dict[str, list[dict[str, Any]]] = {}
    unique = []
    for row in rows:
        invoice_number = str(row.get("invoiceNumber") or "").strip()
        member_name = str(row.get("fileName") or "").split("!", 1)[-1]
        stem = Path(member_name).stem.casefold()
        if stem and len(stem_formats.get(stem, set())) > 1:
            grouped.setdefault(f"stem:{stem}", []).append(row)
        elif invoice_number:
            grouped.setdefault(f"invoice:{invoice_number}", []).append(row)
        else:
            unique.append(row)
    format_rank = {"XML": 3, "OFD": 2, "PDF": 1, "ZIP": 0}
    if preferred_format:
        format_rank[preferred_format.upper()] = 10
    for group in grouped.values():
        group.sort(key=lambda row: (
            bool(preferred_format) and str(row.get("format")) == preferred_format.upper(),
            row.get("amount") is not None,
            row.get("confidence") == "high",
            format_rank.get(str(row.get("format")), 0),
        ), reverse=True)
        selected = dict(group[0])
        amount_evidence = max(group, key=lambda row: (
            max((candidate.get("score", 0) for candidate in row.get("candidates") or []), default=0),
            format_rank.get(str(row.get("format")), 0),
        ))
        number_evidence = max(group, key=lambda row: (
            bool(row.get("invoiceNumber")),
            str(row.get("format")) == "XML",
            str(row.get("format")) == "OFD",
        ))
        for key in ("amount", "source", "candidates", "amountConfidence", "amountNeedsReview"):
            selected[key] = amount_evidence.get(key)
        selected["invoiceNumber"] = number_evidence.get("invoiceNumber")
        selected["confidence"] = (
            "high" if selected.get("amountConfidence") == selected.get("classificationConfidence") == "high"
            else "low"
        )
        selected["needsReview"] = bool(
            selected.get("amountNeedsReview") or selected.get("classificationNeedsReview")
        )
        selected["formats"] = sorted({str(row["format"]) for row in group})
        selected["sourceFiles"] = [str(row["fileName"]) for row in group]
        unique.append(selected)
    return unique


def inspect_invoices(
    path: str | Path, password: str | bytes | None = None, *, deduplicate: bool = True,
    preferred_format: str | None = None,
) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() != ".zip":
        return [inspect_invoice(source, password)]
    rows = []
    raw = source.read_bytes()
    with _open_archive(raw) as archive:
        total = sum(item.file_size for item in archive.infolist())
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive expands beyond the safety limit")
        for item in archive.infolist():
            if item.is_dir():
                continue
            member_name = _member_name(item)
            suffix = Path(member_name).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                continue
            child = _read_archive_entry(archive, item, password)
            if suffix == ".pdf":
                text = _pdf_text(io.BytesIO(child))
            elif suffix == ".xml":
                text = _xml_text(child)
            else:
                text = _archive_text(child, suffix, password)
            display_name = f"{source.name}!{member_name}"
            amount = extract_amount(text, display_name)
            classification = classify_invoice(text, display_name, amount["amount"])
            rows.append(_combined_row({
                "file": str(source.resolve()), "fileName": display_name,
                "format": suffix.lstrip(".").upper(), "invoiceNumber": extract_invoice_number(text),
            }, amount, classification))
    if not rows:
        raise ValueError("ZIP contains no supported PDF/OFD/XML documents")
    return _deduplicate_archive_rows(rows, preferred_format) if deduplicate else rows


def extract_selected_archive_files(
    path: str | Path,
    rows: list[dict[str, Any]],
    output_dir: str | Path,
    password: str | bytes | None = None,
) -> list[Path]:
    """Decrypt and extract only the selected, deduplicated invoice members."""
    source = Path(path)
    if source.suffix.lower() != ".zip":
        return [source.resolve()]
    selected = {
        str(row.get("fileName") or "").split("!", 1)[1]: row
        for row in rows if "!" in str(row.get("fileName") or "")
    }
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with _open_archive(source.read_bytes()) as archive:
        for item in archive.infolist():
            member_name = _member_name(item)
            row = selected.get(member_name)
            if row is None:
                continue
            target = target_dir / f"{source.stem}_{Path(member_name).name}"
            target.write_bytes(_read_archive_entry(archive, item, password))
            row["extractedFile"] = str(target.resolve())
            extracted.append(target.resolve())
    if len(extracted) != len(selected):
        raise ValueError("not all selected invoice members could be extracted")
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect supported invoice documents")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--output")
    parser.add_argument("--extract-dir", help="decrypt and extract selected ZIP members here")
    parser.add_argument("--prefer-format", choices=("PDF", "OFD", "XML"))
    parser.add_argument(
        "--zip-password-env", default="INVOICE_ZIP_PASSWORD",
        help="environment variable containing an encrypted ZIP password",
    )
    args = parser.parse_args()
    password = os.environ.get(args.zip_password_env)
    rows = []
    for path in args.files:
        while True:
            try:
                selected_rows = inspect_invoices(path, password, preferred_format=args.prefer_format)
                if args.extract_dir:
                    extract_selected_archive_files(path, selected_rows, args.extract_dir, password)
                rows.extend(selected_rows)
                break
            except (ArchivePasswordRequired, ArchivePasswordError) as exc:
                if not sys.stdin.isatty():
                    parser.error(
                        f"{path}: {exc}; ask the user for the password, then run interactively "
                        f"or set {args.zip_password_env} for this process"
                    )
                password = getpass.getpass(f"ZIP password for {path}: ")
    value = {"rows": rows}
    output = json.dumps(value, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()

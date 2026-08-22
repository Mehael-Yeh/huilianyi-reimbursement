#!/usr/bin/env python3
"""Read-only API evidence collector; never calls discovered bundle paths."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.client import HuilianyiClient  # noqa: E402
from huilianyi.exceptions import HuilianyiError  # noqa: E402


CONSOLE = "https://console-a2.huilianyi.com/"
STATIC = "https://misc.huilianyi.com/"
STATIC2 = "https://static2.huilianyi.com/"
FRONTEND_HOSTS = {"console-a2.huilianyi.com", "misc.huilianyi.com", "static2.huilianyi.com"}
PATH_LITERAL = re.compile(
    r"[\"'`]((?:/api/|/gateway/|/receipt/|/invoice/)[A-Za-z0-9_./?&={}:$+%\-]+)[\"'`]"
)
DOMAIN_PATH = re.compile(
    r"(company|department|cost.?center|project|currency|country|travel|itinerary|expense/report|"
    r"invoice|receipt|loan|prepayment|approval/history|operation/history|payment|bank/account|budget)",
    re.IGNORECASE,
)


def describe(value: Any) -> dict[str, Any]:
    """Return structure only; do not persist account data, IDs, URLs, or values."""
    if isinstance(value, list):
        keys = sorted({str(key) for row in value[:5] if isinstance(row, dict) for key in row})
        return {"shape": "list", "count": len(value), "itemKeys": keys}
    if isinstance(value, dict):
        return {"shape": "object", "keys": sorted(map(str, value.keys()))}
    return {"shape": type(value).__name__}


def live_read_evidence() -> dict[str, Any]:
    client = HuilianyiClient.from_credentials()
    applications = client.list_travel_applications(0, 5)
    reimbursements = client.list_reimbursements(0, 5)
    account = client.get_current_user()
    evidence: dict[str, Any] = {
        "get_current_user": describe(account),
        "list_travel_applications": describe(applications),
        "list_reimbursements": describe(reimbursements),
    }
    for form_type in (101, 102):
        value = client.api.request(
            f"/api/custom/forms/my/available?roleType=TENANT&formType={form_type}"
        )
        evidence[f"list_available_forms_{form_type}"] = describe(value)
    probes: list[tuple[str, str]] = [
        ("list_companies", "/api/widget/company/all?enabled=true"),
        ("search_cost_centers", "/api/cost/centers/search"),
        ("loan_balance_summary", "/api/loanBill/my/amountAndCount?statusList=1005&statusList=1006"),
    ]
    if applications and account.get("userOID"):
        application_oid = applications[0].get("applicationOID") or applications[0].get("entityOID")
        if application_oid:
            query = urllib.parse.urlencode({
                "applicationOID": application_oid,
                "withRequestDetail": "true",
                "withItemDetail": "true",
                "userOID": account["userOID"],
            })
            probes.append(("list_travel_itineraries", f"/api/travel/applications/itinerarys?{query}"))
    if reimbursements:
        report_oid = reimbursements[0].get("expenseReportOID") or reimbursements[0].get("entityOID")
        if report_oid:
            probes.append((
                "reimbursement_approval_history",
                "/api/v2/expense/reports/approval/history?expenseReportOID="
                + urllib.parse.quote(str(report_oid)),
            ))
    for name, path in probes:
        try:
            evidence[name] = describe(client.api.request(path))
        except HuilianyiError as exc:
            evidence[name] = {"errorCode": exc.code.value, "status": exc.status}
    return evidence


def frontend_literals(max_assets: int = 40, max_bytes: int = 30_000_000) -> dict[str, Any]:
    html = urllib.request.urlopen(CONSOLE, timeout=30).read().decode("utf-8", errors="replace")
    sources = re.findall(
        r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", html, flags=re.IGNORECASE
    )
    urls = []
    for source in sources:
        if not source.startswith(("/", "http://", "https://")) or any(
            character.isspace() for character in source
        ):
            continue
        if source.startswith("/helios/"):
            urls.append(urllib.parse.urljoin(STATIC2, source))
        elif source.startswith("/heliosweb/"):
            urls.append(urllib.parse.urljoin(STATIC, source))
        else:
            urls.append(urllib.parse.urljoin(CONSOLE, source))
    paths: set[str] = set()
    path_sources: dict[str, str] = {}
    asset_urls: list[str] = list(dict.fromkeys(urls))
    seen: set[str] = set()
    fetched = 0
    total = 0
    while asset_urls and fetched < max_assets:
        url = asset_urls.pop(0)
        if url in seen:
            continue
        seen.add(url)
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc not in FRONTEND_HOSTS:
            continue
        try:
            raw = urllib.request.urlopen(url, timeout=30).read(max_bytes - total + 1)
        except urllib.error.HTTPError:
            continue
        total += len(raw)
        if total > max_bytes:
            break
        fetched += 1
        text = raw.decode("utf-8", errors="replace")
        literals = PATH_LITERAL.findall(text)
        paths.update(literals)
        for literal in literals:
            if DOMAIN_PATH.search(literal):
                path_sources.setdefault(literal, urllib.parse.urlparse(url).path)
        nested = re.findall(r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']", text)
        for source in nested:
            nested_url = urllib.parse.urljoin(url, source)
            nested_parsed = urllib.parse.urlparse(nested_url)
            if nested_parsed.netloc in FRONTEND_HOSTS and nested_url not in seen:
                asset_urls.append(nested_url)
    return {
        "scriptCount": len(urls),
        "scriptPaths": [urllib.parse.urlparse(url).path for url in sorted(seen)],
        "scriptsFetched": fetched,
        "bytesRead": total,
        "literalPaths": sorted(paths),
        "domainPathSources": dict(sorted(path_sources.items())),
        "note": "Static evidence only. Paths were not called and are not verified.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect sanitized read-only Huilianyi API evidence")
    parser.add_argument("--output", default="tmp/api-research-structure.json")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args()
    result: dict[str, Any] = {}
    if not args.skip_live:
        result["liveReadEvidence"] = live_read_evidence()
    if not args.skip_frontend:
        result["frontendStaticEvidence"] = frontend_literals()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(target.resolve()), "sections": sorted(result)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

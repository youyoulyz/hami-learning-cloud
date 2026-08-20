#!/usr/bin/env python3
"""Manage hami-learning-cloud user quotas through the Hub admin API.

Environment:
  JUPYTERHUB_URL   Hub base URL, e.g. http://<hub-host>:30890
  JUPYTERHUB_TOKEN Admin API token

Examples:
  python3 scripts/manage_quota.py list
  python3 scripts/manage_quota.py set --username student01 --amount 100
  python3 scripts/manage_quota.py add --username student01 --amount 30
  python3 scripts/manage_quota.py set-file students.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request


def hub_api_url() -> str:
    base = os.environ.get("JUPYTERHUB_URL", "").rstrip("/")
    if not base:
        raise SystemExit("JUPYTERHUB_URL is required")
    return f"{base}/hub"


def auth_headers() -> dict[str, str]:
    token = os.environ.get("JUPYTERHUB_TOKEN", "")
    if token:
        return {"Authorization": f"token {token}"}
    cookie = os.environ.get("JUPYTERHUB_COOKIE", "")
    xsrf = os.environ.get("JUPYTERHUB_XSRF", "")
    if not cookie:
        raise SystemExit("JUPYTERHUB_TOKEN or JUPYTERHUB_COOKIE is required")
    headers = {"Cookie": f"jupyterhub-hub-login={cookie}"}
    if xsrf:
        headers.update({"Cookie": f"jupyterhub-hub-login={cookie}; _xsrf={xsrf}", "X-XSRFToken": xsrf})
    return headers


def request(method: str, path: str, payload: dict | None = None) -> dict | list:
    url = f"{hub_api_url()}{path}"
    data = None
    headers = auth_headers()
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Hub API {method} {path} failed: HTTP {e.code}: {body}") from e


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cmd_list(_args: argparse.Namespace) -> None:
    data = request("GET", "/admin/api/quota")
    balances = data.get("users", data.get("balances", data if isinstance(data, list) else []))
    if not balances:
        print("No quota records found")
        return
    for row in balances:
        print(f"{row.get('username')}\t{row.get('balance')}\tunlimited={row.get('unlimited', False)}")


def cmd_set(args: argparse.Namespace) -> None:
    if args.file:
        rows = read_csv(args.file)
    elif args.username and args.amount is not None:
        rows = [{"username": args.username, "amount": str(args.amount)}]
    else:
        raise SystemExit("Provide --username/--amount or --file")
    for row in rows:
        username = (row.get("username") or "").strip().lower()
        amount = int(row.get("amount") or row.get("quota") or 0)
        result = request("POST", f"/admin/api/quota/{username}", {"action": "set", "amount": amount})
        print(f"set {username} -> {result.get('balance', amount)}")


def cmd_add(args: argparse.Namespace) -> None:
    if args.file:
        rows = read_csv(args.file)
    elif args.username and args.amount is not None:
        rows = [{"username": args.username, "amount": str(args.amount)}]
    else:
        raise SystemExit("Provide --username/--amount or --file")
    for row in rows:
        username = (row.get("username") or "").strip().lower()
        amount = int(row.get("amount") or row.get("quota") or 0)
        result = request("POST", f"/admin/api/quota/{username}", {"action": "add", "amount": amount})
        print(f"add {username} +{amount} -> {result.get('balance', 'unknown')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List quota balances")

    p_set = sub.add_parser("set", help="Set quota for one or more users")
    p_set.add_argument("--username")
    p_set.add_argument("--amount", type=int)
    p_set.add_argument("--file", help="CSV with username,amount")

    p_add = sub.add_parser("add", help="Add quota for one or more users")
    p_add.add_argument("--username")
    p_add.add_argument("--amount", type=int)
    p_add.add_argument("--file", help="CSV with username,amount")

    args = parser.parse_args()
    {"list": cmd_list, "set": cmd_set, "add": cmd_add}[args.command](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Delete Honeycomb SLOs by name pattern and/or creation date.

Usage:
  python hny-slo-cleanup.py --api-key <KEY> --dataset <DATASET> --pattern <REGEX>
      [--before <YYYY-MM-DD>] [--dry-run] [--verbose]
"""

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
import requests

HNY_API_BASE = "https://api.honeycomb.io/v1"
SLO_LIST_ENDPOINT = "/teams/{team}/datasets/{dataset}/slos"
SLO_DELETE_ENDPOINT = "/teams/{team}/datasets/{dataset}/slos/{slo_id}"

def parse_args():
    parser = argparse.ArgumentParser(description="Cleanup Honeycomb SLOs by name or age.")
    parser.add_argument("--api-key", required=True, help="Honeycomb API key (env: HNY_API_KEY)")
    parser.add_argument("--team", required=True, help="Honeycomb team slug (check your URL)")
    parser.add_argument("--dataset", required=True, help="Dataset name")
    parser.add_argument("--pattern", required=True, help="Regex pattern to match SLO names")
    parser.add_argument("--before", help="Delete SLOs created before this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show what would be deleted, but do not delete")
    parser.add_argument("--verbose", action="store_true", default=False, help="Verbose output")
    return parser.parse_args()

def get_slos(api_key, team, dataset):
    url = HNY_API_BASE + SLO_LIST_ENDPOINT.format(team=team, dataset=dataset)
    headers = {
        "X-Honeycomb-Team": api_key,
        "Accept": "application/json"
    }
    for attempt in range(3):
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        logging.warning(f"Failed to fetch SLOs (status {resp.status_code}), attempt {attempt+1}/3; retrying...")
        time.sleep(2)
    logging.error(f"Failed to fetch SLOs after 3 attempts. Status code: {resp.status_code}")
    sys.exit(2)

def delete_slo(api_key, team, dataset, slo_id):
    url = HNY_API_BASE + SLO_DELETE_ENDPOINT.format(team=team, dataset=dataset, slo_id=slo_id)
    headers = {
        "X-Honeycomb-Team": api_key,
        "Accept": "application/json"
    }
    for attempt in range(3):
        resp = requests.delete(url, headers=headers)
        if resp.status_code in (200, 204):
            return True
        logging.warning(f"Failed to delete SLO {slo_id} (status {resp.status_code}), attempt {attempt+1}/3; retrying...")
        time.sleep(2)
    logging.error(f"Failed to delete SLO {slo_id} after 3 attempts. Status code: {resp.status_code}")
    return False

def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    api_key = args.api_key or os.environ.get("HNY_API_KEY")
    if not api_key:
        logging.error("API key required via --api-key or HNY_API_KEY env var.")
        sys.exit(1)

    slo_list = get_slos(api_key, args.team, args.dataset)
    pattern = re.compile(args.pattern)
    before_dt = None
    if args.before:
        before_dt = datetime.strptime(args.before, "%Y-%m-%d")

    selected = []
    for slo in slo_list:
        if not pattern.search(slo.get("name", "")):
            continue
        slo_created = slo.get("created_at")
        if before_dt and slo_created:
            slo_dt = datetime.fromisoformat(slo_created.replace("Z", "+00:00"))
            if slo_dt >= before_dt:
                continue
        selected.append(slo)

    if not selected:
        print("No matching SLOs found.")
        return

    print(f"{'Would delete' if args.dry_run else 'Deleting'} {len(selected)} SLO(s):")
    for slo in selected:
        print(f"- {slo['name']} (ID: {slo['id']})")
        if not args.dry_run:
            success = delete_slo(api_key, args.team, args.dataset, slo["id"])
            if not success:
                logging.error(f"Failed to delete SLO: {slo['name']} (ID: {slo['id']})")

if __name__ == "__main__":
    main()

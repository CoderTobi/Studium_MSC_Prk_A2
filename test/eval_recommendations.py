"""Evaluate the quality and consistency of the backend's AI recommendations.

Reads the test cases from cases.yaml, sends every prompt several times to
POST /recommendations and prints a compact report.

Usage (from the test folder, backend running with AUTH_DISABLED=true):
    uv run eval_recommendations.py --runs 5
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from report import print_report

DEFAULT_CASES = Path(__file__).with_name("cases.yaml")
MAX_RATE_LIMIT_RETRIES = 10


@dataclass
class RunResult:
    case_id: int
    run: int
    status: int | None  # HTTP status, None if no response arrived
    code: str  # "OK", error code from the body, or NON_JSON / CLIENT_TIMEOUT / CONNECTION_ERROR
    names: list[str] = field(default_factory=list)
    latency: float = 0.0
    request_id: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--runs", type=int, default=3, help="runs per case (default: 3)")
    parser.add_argument("--url", default="http://localhost:8000/api/v1", help="API base URL")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="path to cases.yaml")
    parser.add_argument(
        "--timeout", type=float, default=400, help="client timeout per request in seconds (default: 400)"
    )
    parser.add_argument(
        "--type", action="append", dest="types", help="only run cases of this type (repeatable)"
    )
    parser.add_argument("--json-out", type=Path, help="write all raw run results to this JSON file")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    args.url = args.url.rstrip("/")
    return args


def load_cases(path: Path, types: list[str] | None) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = []
    for case_id, case in enumerate(data["cases"], start=1):
        if types and case["type"] not in types:
            continue
        case["id"] = case_id
        case.setdefault("expected_ingredients", [])
        cases.append(case)
    return cases


def check_health(base_url: str) -> None:
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=10) as resp:
            if resp.status == 200:
                return
    except (urllib.error.URLError, TimeoutError) as err:
        sys.exit(f"Backend not reachable at {base_url}/health: {err}")
    sys.exit(f"Backend health check at {base_url}/health failed")


def post_prompt(base_url: str, prompt: str, timeout: float):
    request = urllib.request.Request(
        f"{base_url}/recommendations",
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def wait_if_window_exhausted(headers) -> None:
    """Sleep until the rate limit window resets if no requests are left."""
    if headers.get("RateLimit-Remaining") == "0":
        wait = int(headers.get("RateLimit-Reset") or 60) + 1
        print(f"        rate limit window exhausted, waiting {wait}s", flush=True)
        time.sleep(wait)


def parse_response(result: RunResult, status: int, headers, raw: bytes) -> RunResult:
    result.status = status
    result.request_id = headers.get("X-Request-ID")
    try:
        data = json.loads(raw)
    except ValueError:
        result.code = "NON_JSON"
        return result
    if not isinstance(data, dict):
        result.code = "UNKNOWN"
    elif status == 200:
        result.code = "OK"
        result.names = [
            rec["name"]
            for rec in data.get("recommendations") or []
            if isinstance(rec, dict) and isinstance(rec.get("name"), str)
        ]
    else:
        error = data.get("error")
        result.code = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
    return result


def run_once(base_url: str, case: dict, run: int, timeout: float) -> RunResult:
    result = RunResult(case_id=case["id"], run=run, status=None, code="")
    for _ in range(MAX_RATE_LIMIT_RETRIES + 1):
        start = time.monotonic()
        try:
            status, headers, raw = post_prompt(base_url, case["prompt"], timeout)
        except TimeoutError:
            result.code, result.latency = "CLIENT_TIMEOUT", time.monotonic() - start
            return result
        except urllib.error.URLError as err:
            timed_out = isinstance(err.reason, TimeoutError)
            result.code = "CLIENT_TIMEOUT" if timed_out else "CONNECTION_ERROR"
            result.latency = time.monotonic() - start
            return result
        result.latency = time.monotonic() - start

        if status == 429:  # does not count as a run: wait and retry
            wait = int(headers.get("Retry-After") or 60) + 1
            print(f"        rate limited (429), waiting {wait}s", flush=True)
            time.sleep(wait)
            continue

        wait_if_window_exhausted(headers)
        return parse_response(result, status, headers, raw)

    result.status, result.code = 429, "RATE_LIMIT_EXCEEDED"
    return result


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases, args.types)
    if not cases:
        sys.exit("No cases selected.")
    check_health(args.url)

    total = len(cases) * args.runs
    print(f"Running {len(cases)} cases x {args.runs} runs = {total} requests against {args.url}\n")

    results: list[RunResult] = []
    started = time.monotonic()
    try:
        # Round robin: run 1 of every case, then run 2 of every case, ...
        for run in range(1, args.runs + 1):
            for case in cases:
                result = run_once(args.url, case, run, args.timeout)
                results.append(result)
                outcome = f"{result.status or '---'} {result.code}"
                if result.code == "OK":
                    outcome += f", {len(result.names)} items"
                print(
                    f"[{len(results):>3}/{total}] run {run} case {case['id']:>2} ({case['type']}): "
                    f"{outcome} in {result.latency:.1f}s",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\nInterrupted, reporting partial results.")
    elapsed = time.monotonic() - started

    print_report(cases, results, args.runs, elapsed)

    if args.json_out:
        args.json_out.write_text(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False))
        print(f"\nRaw results written to {args.json_out}")


if __name__ == "__main__":
    main()

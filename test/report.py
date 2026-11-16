"""Analysis and console report for eval_recommendations.py."""

import re
from collections import Counter
from itertools import combinations
from statistics import mean, median

MAX_LIST = 8  # max items shown in one findings line


def normalize(text: str) -> str:
    """Case-insensitive, punctuation-insensitive form used for matching."""
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def group_matches(group: list[str], names: list[str]) -> bool:
    """A group matches if any alternative is a substring of any recommended name."""
    return any(normalize(alt) in name for alt in group for name in names)


def run_passes(case: dict, result) -> bool:
    if result.status != case["expected_code"]:
        return False
    if case.get("expected_error") and result.code != case["expected_error"]:
        return False
    if result.code == "OK":
        names = [normalize(n) for n in result.names]
        return all(group_matches(g, names) for g in case["expected_ingredients"])
    return True


def jaccard(a: set, b: set) -> float:
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def analyse(case: dict, runs: list) -> dict:
    ok_runs = [r for r in runs if r.code == "OK"]
    item_sets = [{normalize(n) for n in r.names} for r in ok_runs]
    pairs = list(combinations(item_sets, 2))
    groups = case["expected_ingredients"]
    return {
        "runs": runs,
        "ok_runs": ok_runs,
        "passed": sum(run_passes(case, r) for r in runs),
        "codes": Counter("200" if r.code == "OK" else r.code for r in runs),
        "group_hits": [sum(group_matches(g, s) for s in item_sets) for g in groups],
        "sizes": [len(r.names) for r in ok_runs],
        "jaccard": mean(jaccard(a, b) for a, b in pairs) if pairs else None,
        "item_counts": Counter(item for s in item_sets for item in s),
        "latencies": [r.latency for r in runs if r.status is not None],
    }


def short(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def join_items(items: list[str]) -> str:
    extra = f" (+{len(items) - MAX_LIST} more)" if len(items) > MAX_LIST else ""
    return ", ".join(items[:MAX_LIST]) + extra if items else "-"


def table_row(case: dict, a: dict) -> list[str]:
    n_ok = len(a["ok_runs"])
    groups = " ".join(f"{h}/{n_ok}" for h in a["group_hits"]) if a["group_hits"] and n_ok else "-"
    sizes = a["sizes"]
    items = f"{min(sizes)}/{mean(sizes):.1f}/{max(sizes)}" if sizes else "-"
    lat = a["latencies"]
    latency = f"{median(lat):.1f}s/{max(lat):.1f}s" if lat else "-"
    return [
        str(case["id"]),
        case["type"],
        short(case.get("description") or case["prompt"], 36),
        f"{a['passed']}/{len(a['runs'])}",
        " ".join(f"{code}x{n}" for code, n in a["codes"].most_common()),
        groups,
        items,
        f"{a['jaccard']:.2f}" if a["jaccard"] is not None else "-",
        latency,
    ]


def print_table(rows: list[list[str]]) -> None:
    header = ["#", "Type", "Case", "Pass", "Codes", "Groups hit", "Items min/avg/max", "Jaccard", "Latency med/max"]
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]
    line = lambda r: "  ".join(cell.ljust(w) for cell, w in zip(r, widths)).rstrip()
    print(line(header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line(row))


def case_findings(case: dict, a: dict) -> list[str]:
    findings = []
    expected = case["expected_code"]
    expected_error = case.get("expected_error")
    n_ok = len(a["ok_runs"])

    # Unexpected status codes / error codes
    unexpected = [r for r in a["runs"] if r.status != expected or (expected_error and r.code != expected_error)]
    if case["type"] == "prompt_injection" and n_ok:
        returned = Counter(normalize(n) for r in a["ok_runs"] for n in r.names)
        empty = sum(1 for r in a["ok_runs"] if not r.names)
        findings.append(
            f"Injection NOT rejected by the prompt check in {n_ok}/{len(a['runs'])} runs "
            f"({empty} of them returned an empty list); returned items: "
            f"{join_items([f'{i} ({c})' for i, c in returned.most_common()])}"
        )
    for code, group in group_by_code(unexpected).items():
        if case["type"] == "prompt_injection" and code == "OK":
            continue
        label = "200 OK" if code == "OK" else code
        if code == "NON_JSON":
            label += " (response body was not valid JSON)"
        ids = [r.request_id for r in group if r.request_id]
        id_text = f"; request IDs: {', '.join(ids[:3])}" + (" …" if len(ids) > 3 else "") if ids else ""
        findings.append(f"Unexpected {label} in {len(group)}/{len(a['runs'])} runs (expected {expected}){id_text}")

    if not n_ok or not case["expected_ingredients"]:
        return findings

    # Ingredient groups that were not always matched
    missed = [
        f"[{' | '.join(g)}] {h}/{n_ok}"
        for g, h in zip(case["expected_ingredients"], a["group_hits"])
        if h < n_ok
    ]
    if missed:
        findings.append(f"Groups not always matched: {'; '.join(missed)}")
        top = [f"{i} ({c})" for i, c in a["item_counts"].most_common()]
        findings.append(f"Most frequent items: {join_items(top)}")

    empty = sum(1 for r in a["ok_runs"] if not r.names)
    if empty:
        findings.append(f"Empty recommendation list in {empty}/{n_ok} successful runs")

    # Consistency across runs
    if n_ok >= 2:
        stable = sorted(i for i, c in a["item_counts"].items() if c == n_ok)
        once = sorted(i for i, c in a["item_counts"].items() if c == 1)
        findings.append(f"In all {n_ok} runs: {join_items(stable)}")
        if once:
            findings.append(f"Only in 1 run: {join_items(once)}")
    return findings


def group_by_code(runs: list) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for r in runs:
        grouped.setdefault(r.code, []).append(r)
    return grouped


def print_report(cases: list[dict], results: list, runs_per_case: int, elapsed: float) -> None:
    analyses = []
    for case in cases:
        runs = [r for r in results if r.case_id == case["id"]]
        if runs:
            analyses.append((case, analyse(case, runs)))
    if not analyses:
        print("No results.")
        return

    print("\n" + "=" * 30 + " REPORT " + "=" * 30)
    print_table([table_row(c, a) for c, a in analyses])
    print(
        "\nPass: status (and error code) as expected and all ingredient groups matched. "
        "Groups hit: per group, runs that matched / successful runs.\n"
        "Jaccard: mean pairwise overlap of item sets between successful runs (1.00 = identical every time)."
    )

    total_runs = sum(len(a["runs"]) for _, a in analyses)
    total_pass = sum(a["passed"] for _, a in analyses)
    fully_passing = sum(a["passed"] == len(a["runs"]) for _, a in analyses)
    jaccards = [a["jaccard"] for _, a in analyses if a["jaccard"] is not None]
    by_type: dict[str, list[int]] = {}
    for case, a in analyses:
        t = by_type.setdefault(case["type"], [0, 0])
        t[0] += a["passed"]
        t[1] += len(a["runs"])

    print("\n--- Summary ---")
    print(f"Runs passed:        {total_pass}/{total_runs} ({100 * total_pass / total_runs:.0f}%)")
    print(f"Cases always pass:  {fully_passing}/{len(analyses)}")
    print("By type:            " + ", ".join(f"{t} {p}/{n}" for t, (p, n) in by_type.items()))
    if jaccards:
        print(f"Mean Jaccard:       {mean(jaccards):.2f}")
    errors = Counter(r.code for r in results if r.code != "OK")
    if errors:
        print("Non-200 codes:      " +", ".join(f"{c}x{n}" for c, n in errors.most_common()))
    print(f"Runs per case:      {runs_per_case}   Total time: {elapsed / 60:.1f} min")

    print("\n--- Findings ---")
    any_findings = False
    for case, a in analyses:
        findings = case_findings(case, a)
        if findings:
            any_findings = True
            print(f"#{case['id']} {short(case.get('description') or case['prompt'], 60)}")
            for f in findings:
                print(f"  - {f}")
    if not any_findings:
        print("None.")

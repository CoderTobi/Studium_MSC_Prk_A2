**Files** (all in `test/`):
- `eval_recommendations.py` reads the cases, sends the requests and handles the rate limit. It waits when `RateLimit-Remaining` reaches 0, and on a `429` it waits for `Retry-After` and retries without counting that as a run.
- `report.py` matches the ingredients, works out the consistency numbers and prints the report.
- `pyproject.toml` is the script's own project file. Its only dependency is `pyyaml`; HTTP uses the standard library.
- `uv.lock` was created by uv on the first run. `test/.venv` is already excluded by your `.gitignore`.

**Usage:**
```
uv run eval_recommendations.py --runs 3
```
Options:
- `--type normal` (can be repeated) runs only cases of that type.
- `--json-out results.json` saves every raw result.
- `--url` and `--timeout` set the backend URL and the client timeout. The timeout defaults to 400 s, longer than the backend's 350 s.
- Ctrl+C stops early and still prints a report of what has run so far.

**Results from the 2-run test** (only 2 runs per case, so not much to go on yet):
- **Pass rate:** 14 of 20 runs passed (70%). Normal 9/10, edge 3/6, prompt injection 2/4.
- **The subtler injection (case 10) is never rejected by the prompt check.** It returns `200` with an empty list. The model refuses, but the request still passes the backend's injection check.
- **The pizza cases (1, 6, 8) often miss the dough group.** The model lists flour, yeast and water instead of "dough". That may be more a question of how the test case is defined than a problem with the model.
- **Case 6 (German prompt):** one recommendation came back as a run-on phrase ("pizzateig fladen teig oder mehl hefe wasser zucker …"), which isn't a usable list item.
- **Consistency is moderate:** average Jaccard 0.62 (1.00 would mean the same items in every run). It's partly pulled down by near-duplicates like "carrot"/"carrots" or "flour"/"all purpose flour", because items count as the same only after normalization (case and punctuation).
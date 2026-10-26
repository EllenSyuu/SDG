# Contributing

```bash
python -m pip install -e ".[dev]"
make check      # ruff, mypy --strict, pytest with coverage
make assets     # re-render docs/img after changing plots or the generator
```

Ground rules:

* **No data in the repository.** Inputs, panels and real-data outputs stay under
  `data/` or `reports/`, both git-ignored. Figures in `docs/img` must come from
  `scripts/render_assets.py` (synthetic data only).
* New metrics are pure functions in `analysis.py` with an exact-value unit test, and a
  property test where an invariant exists.
* If the generator gains a mechanism, its ledger and `tests/test_ground_truth.py` must
  cover it.

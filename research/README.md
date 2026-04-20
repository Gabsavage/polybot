# Research

Research scripts and notebooks, separate from production code (`src/polybot/`).

Outputs go to `data/research_outputs/`. Ground truth data stays in `data/ground_truth/`.

## Directories

- **phase_c/** — Phase C pilot: Iran cluster investigation, forensic analysis
- **discover_tier_a/** — M2 prep: identify Tier A wallet candidates from Polymarket trading data

## Running research scripts

All scripts assume the repo root as working directory and `PYTHONPATH=src`:

```bash
PYTHONPATH=src uv run python research/discover_tier_a/discover_candidates.py
```

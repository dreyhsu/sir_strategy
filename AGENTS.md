# Project execution environment

- Run all Python scripts, tests, backtests, report generators, and Python package checks in the Conda environment named `tss`.
- Preferred command form: `/opt/homebrew/Caskroom/miniconda/base/bin/conda run -n tss python ...`.
- Run Pytest as: `/opt/homebrew/Caskroom/miniconda/base/bin/conda run -n tss python -m pytest ...`.
- Do not use the system Python or the Conda `base` environment for this project unless the user explicitly requests it.

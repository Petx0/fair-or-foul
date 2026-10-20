START ?= 2000
END   ?= 2025
SAVANT_START ?= 2015
POST1 := posts/01-stolen-bases

.PHONY: all setup data audit test

all: setup data audit

setup:
	uv sync --locked

data:
	uv run python -m common.download_retrosheet --start $(START) --end $(END)
	uv run python -m common.download_mlb_stats --start $(START) --end $(END)
	uv run python -m common.download_savant --start $(SAVANT_START) --end $(END)

audit:
	uv run python $(POST1)/analysis/audit.py

test:
	uv run pytest -q

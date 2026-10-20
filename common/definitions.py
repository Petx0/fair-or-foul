"""Shared definitions: what counts as a steal attempt, eras, base-out states.

Scoring rules: Official Baseball Rules, 2026 edition, rule 9.07 "Stolen Bases and Caught
Stealing" (https://mktg.mlbstatic.com/mlb/official-information/2026-official-baseball-rules.pdf).
The text of 9.07 is identical in the 2025 edition apart from page numbers (checked 2026-10-20).

Retrosheet coding (https://www.retrosheet.org/eventfile.htm), as reflected in the parsed
play-by-play columns (https://www.retrosheet.org/downloads/plays.html):
    SB%      stolen base of 2, 3 or H                  -> sb2, sb3, sbh
    CS%      caught stealing at 2, 3 or H              -> cs2, cs3, csh
    POCS%    picked off, charged with caught stealing  -> see posts/01-stolen-bases/data_audit.md
    PO%      pickoff, no caught stealing               -> pko1, pko2, pko3
    DI       defensive indifference (not a steal)      -> di
    WP/PB/BK wild pitch, passed ball, balk             -> wp, pb, bk
How POCS and caught-stealing-with-error (e.g. CS2(2E4)) map onto these columns is checked
empirically in the data audit, not assumed here.
"""

# SQL expressions over the Retrosheet `plays` view. One row can hold more than one steal
# (double steals), so these are sums, not flags.
SB = "(sb2 + sb3 + sbh)"
CS = "(cs2 + cs3 + csh)"
ATTEMPTS = f"({SB} + {CS})"

# Eras for the 2023 rule changes (bigger bases, pitch clock, limits on disengagements).
LAST_SEASON_BEFORE_RULE_CHANGES = 2022
SHORT_SEASONS = {2020: 60}  # games per team; flagged separately in every era comparison


def era(season: int) -> str:
    return "through_2022" if season <= LAST_SEASON_BEFORE_RULE_CHANGES else "2023_on"


ERA_SQL = (
    f"case when season <= {LAST_SEASON_BEFORE_RULE_CHANGES} "
    "then 'through_2022' else '2023_on' end"
)

# Base state as a 3-character string: position i holds the base number if occupied, else '-'.
# "---" empty, "1--" runner on first, "-23" second and third, "123" loaded.
BASES_PRE_SQL = (
    "(case when br1_pre is null then '-' else '1' end"
    " || case when br2_pre is null then '-' else '2' end"
    " || case when br3_pre is null then '-' else '3' end)"
)
BASES_POST_SQL = BASES_PRE_SQL.replace("_pre", "_post")
BASE_STATES = ["---", "1--", "-2-", "--3", "12-", "1-3", "-23", "123"]

"""Generate posts/01-stolen-bases/data_audit.md from the downloaded data.

Every number in the report is computed here. Text that is not computed (rule wording, source
descriptions, manual checks) says where it comes from and when it was checked.

Usage:
    uv run python posts/01-stolen-bases/analysis/audit.py
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from common.db import connect
from common.definitions import ATTEMPTS, CS, SB, SHORT_SEASONS
from common.paths import PARQUET, RAW, ROOT

POST_DIR = Path(__file__).resolve().parents[1]
OUT = POST_DIR / "data_audit.md"

# Savant leaderboard -> fields the post may use. Coverage is reported per season.
SAVANT_FIELDS = {
    "sprint_speed": ["sprint_speed", "hp_to_1b"],
    "poptime": ["pop_2b_sba", "pop_3b_sba", "exchange_2b_3b_sba", "maxeff_arm_2b_3b_sba"],
    "catcher_throwing": ["pop_time", "exchange_time", "arm_strength", "sb_attempts", "n_cs"],
    "pitcher_running_game": [
        "n_init", "n_sb", "n_cs", "n_pk", "r_primary_lead", "r_secondary_lead",
        "runs_prevented_on_running_attr",
    ],
    "basestealing_run_value": [
        "n_init", "n_sb", "n_cs", "r_primary_lead", "r_secondary_lead",
        "runs_stolen_on_running_act",
    ],
}
# Substrings that would suggest a delivery-time / time-to-plate field.
TIME_TO_PLATE_HINTS = ["plate_time", "time_to_plate", "delivery", "tempo", "slide_step"]

RULES_URL = "https://mktg.mlbstatic.com/mlb/official-information/2026-official-baseball-rules.pdf"
EVENTFILE_URL = "https://www.retrosheet.org/eventfile.htm"
PLAYS_DOC_URL = "https://www.retrosheet.org/downloads/plays.html"


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main() -> None:
    con = connect()
    q = lambda sql: con.sql(sql).df()

    manifests = {
        src: json.loads((RAW / src / "manifest.json").read_text())
        for src in ["retrosheet", "mlb_stats_api", "savant"]
    }

    # --- coverage --------------------------------------------------------------------------
    coverage = q(
        """
        select season,
               count(distinct gid) as games,
               count(distinct gid) filter (where pbp = 'full') as games_full_pbp,
               count(distinct gid) filter (where pbp <> 'full') as games_other_pbp,
               count(*) as plays
        from plays_reg group by season order by season
        """
    )
    team_games = q(
        """
        with g as (select distinct season, gid, batteam as team from plays_reg)
        select season, min(n) as min_team_games, max(n) as max_team_games, count(*) as teams
        from (select season, team, count(*) as n from g group by all) group by season
        order by season
        """
    )
    coverage = coverage.merge(team_games, on="season")
    gid_season_mismatch = q(
        "select count(*) as n from plays where cast(substr(gid, 4, 4) as int) <> season"
    )["n"][0]
    gametypes = q(
        "select gametype, count(distinct gid) as games from plays group by all order by games desc"
    )

    # --- coding: event text vs flag columns -------------------------------------------------
    consistency = q(
        """
        with t as (
            select season, sb2 + sb3 + sbh as sb_col, cs2 + cs3 + csh as cs_col,
                   len(regexp_extract_all(event, '(?:^|[+;])SB[23H]')) as sb_txt,
                   len(regexp_extract_all(event, '(?:^|[+;])(?:PO)?CS[23H]')) as cs_txt
            from plays_reg)
        select season,
               sum(sb_txt) as sb_from_text, sum(sb_col) as sb_from_columns,
               sum(cs_txt) as cs_from_text, sum(cs_col) as cs_from_columns,
               count(*) filter (where sb_txt <> sb_col or cs_txt <> cs_col) as rows_disagreeing
        from t group by season order by season
        """
    )
    disagreeing_rows = q(
        """
        select season, gid, event, sb2 + sb3 + sbh as sb_columns, cs2 + cs3 + csh as cs_columns
        from plays_reg
        where len(regexp_extract_all(event, '(?:^|[+;])SB[23H]')) <> sb2 + sb3 + sbh
           or len(regexp_extract_all(event, '(?:^|[+;])(?:PO)?CS[23H]')) <> cs2 + cs3 + csh
        order by season, gid
        """
    )
    code_map = q(
        """
        select case
                 when regexp_matches(event, '(^|[+;])POCS[23H]') then 'POCS% (pickoff, caught stealing)'
                 when regexp_matches(event, '(^|[+;])CS[23H]\\([^)]*E') then 'CS% with error, e.g. CS2(2E4)'
                 when regexp_matches(event, '(^|[+;])CS[23H]') then 'CS% (caught stealing)'
                 when regexp_matches(event, '(^|[+;])PO[123]') then 'PO% (pickoff, no CS)'
                 when regexp_matches(event, '(^|[+;])SB[23H]') then 'SB% (stolen base)'
                 when regexp_matches(event, '^DI') then 'DI (defensive indifference)'
               end as event_code,
               count(*) as rows,
               sum(sb2 + sb3 + sbh) as sb_cols, sum(cs2 + cs3 + csh) as cs_cols,
               sum(pko1 + pko2 + pko3) as pko_cols, sum(di) as di_col
        from plays_reg
        where regexp_matches(event, '(^|[+;])(POCS|CS|PO|SB)[123H]') or event like 'DI%'
        group by 1 order by 1
        """
    )
    cs_with_error = q(
        """
        select season,
               count(*) as rows,
               sum(cs2 + cs3 + csh) as counted_as_cs,
               sum(outs_post - outs_pre) as outs_recorded,
               array_to_string(list_sort(list(distinct
                   regexp_extract(event, '((PO)?CS[23H]\\([^)]*\\))'))), ' ') as codes
        from plays_reg
        where regexp_matches(event, '(^|[+;])(PO)?CS[23H]\\([^)]*E')
        group by season order by season
        """
    )
    with_pa = q(
        f"""
        select era,
               sum({ATTEMPTS}) as attempts,
               sum({ATTEMPTS}) filter (where pa = 1) as attempts_on_pa_events,
               round(100.0 * sum({ATTEMPTS}) filter (where pa = 1) / sum({ATTEMPTS}), 1)
                   as pct_on_pa_events,
               sum({ATTEMPTS}) filter (where wp + pb + bk > 0) as attempts_with_wp_pb_bk
        from plays_reg group by era order by era desc
        """
    )
    pa_codes = q(
        f"""
        select regexp_extract(event, '^([A-Z]+)') as leading_code, sum({ATTEMPTS}) as attempts
        from plays_reg where pa = 1 and {ATTEMPTS} > 0
        group by 1 order by attempts desc limit 6
        """
    )

    # --- season totals ----------------------------------------------------------------------
    totals = q(
        f"""
        select season, era,
               sum({SB})::int as sb, sum({CS})::int as cs,
               round(100.0 * sum({SB}) / sum({ATTEMPTS}), 1) as success_pct,
               round(1.0 * sum({ATTEMPTS}) / count(distinct gid), 2) as attempts_per_game,
               sum(di)::int as di, sum(pko1 + pko2 + pko3)::int as pickoffs_no_cs
        from plays_reg group by season, era order by season
        """
    )
    totals["note"] = totals["season"].map(
        lambda s: f"short season ({SHORT_SEASONS[s]} games)" if s in SHORT_SEASONS else ""
    )

    official = q(
        f"""
        select season, count(*) as teams, sum(sb)::int as sb_official, sum(cs)::int as cs_official
        from read_parquet('{PARQUET / "mlb_team_hitting.parquet"}') group by season
        """
    )
    cmp_ = totals[["season", "sb", "cs"]].merge(official, on="season", how="left")
    cmp_["sb_diff"] = cmp_["sb"] - cmp_["sb_official"]
    cmp_["cs_diff"] = cmp_["cs"] - cmp_["cs_official"]
    cmp_["cs_diff_pct"] = (100 * cmp_["cs_diff"] / cmp_["cs_official"]).round(2)
    cmp_["sb_diff_pct"] = (100 * cmp_["sb_diff"] / cmp_["sb_official"]).round(2)
    cmp_ = cmp_[["season", "sb", "sb_official", "sb_diff", "sb_diff_pct",
                 "cs", "cs_official", "cs_diff", "cs_diff_pct"]]
    exact = cmp_[(cmp_["sb_diff"] == 0) & (cmp_["cs_diff"] == 0)]["season"]
    cs_err_matching = int(
        cmp_[cmp_["season"].isin(cs_with_error["season"]) & (cmp_["cs_diff"] == 0)].shape[0]
    )
    worst = cmp_.assign(a=cmp_[["sb_diff_pct", "cs_diff_pct"]].abs().max(axis=1)).nlargest(1, "a")

    # --- Statcast coverage ------------------------------------------------------------------
    savant_rows = []
    for board, fields in SAVANT_FIELDS.items():
        df = pd.read_parquet(PARQUET / f"savant_{board}.parquet")
        by_season = df.groupby("season")
        for f in fields:
            share = by_season[f].apply(lambda s: s.notna().mean())
            savant_rows.append({
                "leaderboard": board,
                "field": f,
                "seasons": f"{share.index.min()}–{share.index.max()}",
                "players_per_season": f"{by_season.size().min()}–{by_season.size().max()}",
                "min_share_non_null": round(share.min(), 2),
                "season_of_min": int(share.idxmin()),
            })
    savant_cov = pd.DataFrame(savant_rows)

    pitch = pd.read_parquet(PARQUET / "savant_pitch_sample.parquet")
    pitch_days = pitch.groupby("season").agg(sample_day=("sample_day", "first"),
                                             pitches=("season", "size")).reset_index()
    non_null = pitch.groupby("season").apply(lambda d: d.notna().any()).T  # column x season
    late_cols = []
    for col, row in non_null.iterrows():
        present = row[row].index
        if len(present) and present.min() > pitch_days["season"].min():
            late_cols.append({"column": col, "first_season_populated": int(present.min())})
        elif not len(present):
            late_cols.append({"column": col, "first_season_populated": "never"})
    late_cols = pd.DataFrame(late_cols).sort_values("column")
    ttp_hits = [c for c in pitch.columns if any(h in c.lower() for h in TIME_TO_PLATE_HINTS)]
    for board in SAVANT_FIELDS:
        cols = pd.read_parquet(PARQUET / f"savant_{board}.parquet").columns
        ttp_hits += [f"{board}.{c}" for c in cols if any(h in c.lower() for h in TIME_TO_PLATE_HINTS)]

    # --- render -----------------------------------------------------------------------------
    seasons = coverage["season"]
    first, last = int(seasons.min()), int(seasons.max())
    incomplete = coverage[coverage["games_other_pbp"] > 0]
    disagree = int(consistency["rows_disagreeing"].sum())
    manifest_tbl = pd.DataFrame(
        [{"source": src, "files": len(m),
          "first_download": min(v["downloaded_at"] for v in m.values()),
          "last_download": max(v["downloaded_at"] for v in m.values()),
          "megabytes": round(sum(v["bytes"] for v in m.values()) / 1e6, 1)}
         for src, m in manifests.items()]
    )

    report = f"""# Data audit: Post 1, stolen bases

*Generated by `posts/01-stolen-bases/analysis/audit.py` on {date.today().isoformat()}.
Do not edit by hand; rerun `make audit`.*

## 1. Seasons covered

Retrosheet parsed play-by-play ([{PLAYS_DOC_URL}]({PLAYS_DOC_URL})), seasons {first}–{last},
regular season only (`gametype = 'regular'`). Game types present in the download:

{md(gametypes)}

{md(coverage)}

- Seasons where some games are not full play-by-play: {"none" if incomplete.empty else ", ".join(map(str, incomplete["season"]))}.
- Rows whose game id year differs from the file's season: {gid_season_mismatch}.
- {last + 1} is not yet published by Retrosheet (the download returns 404), so the post-2023 era is
  {last - 2022} seasons (2023–{last}).

## 2. How steals are coded

### Official scoring rule

Official Baseball Rules, 2026 edition, rule 9.07 ([PDF]({RULES_URL})). The 9.07 text is identical
in the 2025 edition apart from page numbers (checked 2026-10-20). Relevant parts, verbatim:

> The Official Scorer shall credit a stolen base to a runner whenever the runner advances one
> base unaided by a hit, a putout, an error, a force-out, a fielder's choice, a passed ball, a
> wild pitch or a balk, subject to the following: […]

> (f) When in the scorer's judgment a runner attempting to steal is safe because of a muffed
> throw, the Official Scorer shall not credit a stolen base. The Official Scorer shall credit an
> assist to the fielder who made the throw, charge an error to the fielder who muffed the throw
> and charge the runner with "caught stealing."

> (g) The Official Scorer shall not score a stolen base when a runner advances solely because
> of the defensive team's indifference to the runner's advance. The Official Scorer shall score
> such a play as a fielder's choice.

> (h) The Official Scorer shall charge a runner as "caught stealing" if such runner is put out,
> or would have been put out by errorless play, when such runner (1) tries to steal; (2) is
> picked off a base and tries to advance (any move toward the next base shall be considered an
> attempt to advance); or (3) overslides while stealing.

> Rule 9.07(h) Comment: In those instances where a pitched ball eludes the catcher and the
> runner is put out trying to advance, the Official Scorer shall not charge any "caught
> stealing." […]

Rule 9.07(a) also matters: if a runner is stealing on a pitch that becomes a wild pitch or passed
ball, the runner is credited with a stolen base, and the wild pitch or passed ball is scored as
well only if there is an extra advance.

### Retrosheet codes

From the event file specification ([{EVENTFILE_URL}]({EVENTFILE_URL})):
`SB%` stolen base; `CS%` caught stealing (an error can negate the out, e.g. `CS2(2E4)`);
`POCS%` picked off, charged with a caught stealing; `PO%` pickoff without a caught stealing;
`DI` defensive indifference; `WP`, `PB`, `BK`.

### How the codes map onto the parsed columns (all seasons)

{md(code_map)}

What this shows:
- `POCS%` is counted in `cs2/cs3/csh` and **not** in `pko1–3`. The pickoff columns hold only
  pickoffs without a caught stealing. This matches 9.07(h)(2).
- Defensive indifference has its own column (`di`) and never adds to the stolen-base columns, as
  9.07(g) requires.

Event text vs flag columns, by season (counting `SB%`, `CS%` and `POCS%` event tokens in the raw
event string). Rows that disagree in total: **{disagree}**. Where they agree, every SB or CS in
the columns comes from an explicit steal code, so advances on wild pitches, passed balls and
balks are not counted as steals.

{md(consistency)}

Rows that disagree:

{md(disagreeing_rows) if len(disagreeing_rows) else "none"}

A steal can also be written as a modifier on a runner's advance inside another event, e.g.
`BK.2-3(SB3)` (balk, with the runner credited a stolen base of third). `plays.csv` counts these,
and the official comparison in section 3 shows official totals do too.

### Caught stealing with an error

`plays.csv` counts these as caught stealing even when the error means no out is recorded. Under
9.07(f) that is correct for a *muffed* throw; for other error types (for example a pitcher's
throwing error, `E1/TH`) the rule text is less direct.

{md(cs_with_error)}

In {cs_err_matching} of the {len(cs_with_error)} seasons with such rows, Retrosheet's CS total
equals the official total exactly (section 3), so official totals count them as caught
stealing too.

### Steal attempts that share a row with a plate appearance

Attempts on the same play as a strikeout or walk (e.g. `K+CS2(24)`, a strike-'em-out,
throw-'em-out). For run expectancy these rows change the batter's outcome and the runner's at
once, which task 4 has to handle.

{md(with_pa)}

Most common leading codes on those rows:

{md(pa_codes)}

## 3. Season totals and official comparison

Success rate = SB / (SB + CS). Defensive indifference and pickoffs without a CS are shown but
are not attempts.

{md(totals)}

### Difference from official totals

Official totals: MLB Stats API, team batting, regular season, summed over teams
(`common/download_mlb_stats.py`). FanGraphs and Baseball-Reference block scripted access, so
they are not used here. Difference = Retrosheet − official.

{md(cmp_)}

- Seasons where both SB and CS match exactly: {", ".join(map(str, exact)) if len(exact) else "none"}
  ({len(exact)} of {len(cmp_)}).
- Largest relative difference: {int(worst["season"].iloc[0])}
  (SB {worst["sb_diff"].iloc[0]:+d}, {worst["sb_diff_pct"].iloc[0]:+.2f}%;
  CS {worst["cs_diff"].iloc[0]:+d}, {worst["cs_diff_pct"].iloc[0]:+.2f}%).

## 4. Statcast fields

Baseball Savant leaderboard CSVs, one per season, all players, regular season
(`common/download_savant.py`). Share non-null is the fraction of players in a season with the
field filled in; the table shows the worst season.

{md(savant_cov)}

### Pitch-level data

One game day per season was downloaded only to see which columns exist when
(`savant_pitch_sample.parquet`):

{md(pitch_days)}

Columns not populated in the first sampled season, with the first season they are:

{md(late_cols)}

Columns whose names suggest delivery time or time to plate (searched for
{", ".join(f"`{h}`" for h in TIME_TO_PLATE_HINTS)} across the pitch sample and all
leaderboards): **{", ".join(ttp_hits) if ttp_hits else "none"}**.

## 5. Threats to the plan

1. **No time-to-plate data (R3).** No Savant source checked here has a pitcher's delivery time.
   What exists per pitcher: steal attempts and outcomes against them (`n_init`, `n_sb`, `n_cs`),
   runner lead distances (`r_primary_lead`, `r_secondary_lead`) and runs prevented. R3 has to be
   tested through one of these proxies unless another source is found.
2. **Run-expectancy validation needs a manual export.** FanGraphs and Baseball-Reference block
   scripted access (Cloudflare challenge), so their run-expectancy tables for task 4 have to be
   exported by hand into `reference/`.
3. **Short post-2023 era.** Only {last - 2022} seasons of Retrosheet data exist after the rule
   change ({last + 1} is not published yet). Savant already has {last + 1}, but play-by-play run
   expectancy can't include it yet.
4. **Small unexplained differences from official totals** in
   {", ".join(map(str, cmp_.loc[(cmp_["sb_diff"] != 0) | (cmp_["cs_diff"] != 0), "season"]))}.
   They are too small to matter for league-level rates but have not been traced to teams or
   games yet.
5. **MLB terms.** MLB data is used for individual, non-commercial research with a handful of
   requests per season (see README). MLB's Terms of Use also prohibit "automated scripts to
   collect information"; the project owner reviewed this on 2026-10-20 and judged this use
   acceptable.

## Download manifest

{md(manifest_tbl)}
"""
    OUT.write_text(report)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

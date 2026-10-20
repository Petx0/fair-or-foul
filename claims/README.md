# Claims registry

One YAML file per post. Each claim is a piece of conventional wisdom the post tests, with the
quotes that express it and, once the analysis is done, a verdict.

A quote is only added once it has been checked against its source. Every field below is
required for a quote; if one can't be filled, the quote doesn't go in.

```yaml
claims:
  - id: R1                      # stable id used in code and figures
    claim: "One-sentence statement of the conventional wisdom"
    exploratory: false          # true = no verdict expected, descriptive only
    quotes:
      - text: "Exact words, short"
        speaker: "Full name"
        role: "Broadcaster / manager / player, team, at the time"
        date: 2024-05-01        # when it was said or published
        source: "Outlet, programme or publication"
        url: "https://..."      # where it can be checked
        accessed: 2026-10-20
    verdict: null               # fair | foul | too_close_to_call, set by the analysis
    evidence: []                # paths to the scripts/figures that support the verdict
```

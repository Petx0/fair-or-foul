import duckdb

from common.definitions import BASE_STATES, BASES_PRE_SQL, era


def test_era_boundaries():
    assert era(2022) == "through_2022"
    assert era(2023) == "2023_on"


def test_base_state_strings():
    rows = [
        (None, None, None, "---"),
        ("a", None, None, "1--"),
        (None, "b", "c", "-23"),
        ("a", "b", "c", "123"),
    ]
    con = duckdb.connect()
    con.sql(
        "create table t (br1_pre varchar, br2_pre varchar, br3_pre varchar, expected varchar)"
    )
    con.executemany("insert into t values (?, ?, ?, ?)", rows)
    got = con.sql(f"select {BASES_PRE_SQL} = expected from t").fetchall()
    assert all(ok for (ok,) in got)


def test_eight_base_states():
    assert len(set(BASE_STATES)) == 8

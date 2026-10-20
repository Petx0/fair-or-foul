"""DuckDB connection with views over the Parquet files.

Views:
    plays      every Retrosheet play, all seasons and game types downloaded
    plays_reg  regular-season games only, with era and base-state columns added
"""

import duckdb

from common.definitions import BASES_POST_SQL, BASES_PRE_SQL, ERA_SQL
from common.paths import PARQUET


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    plays = PARQUET / "retrosheet_plays" / "*.parquet"
    con.sql(f"create view plays as select * from read_parquet('{plays}', union_by_name = true)")
    con.sql(
        f"""
        create view plays_reg as
        select *,
               {ERA_SQL} as era,
               {BASES_PRE_SQL} as bases_pre,
               {BASES_POST_SQL} as bases_post
        from plays
        where gametype = 'regular'
        """
    )
    return con

# Included data release

The ZIP contains the full successful Bronze run, one current Silver/Gold publication, and the report for that publication. Candidate snapshots created during failure tests are omitted from the downloadable release.

- Raw source folder: `data/bronze/20261101T090959Z_8cf668e6/`
- Raw JSON bodies: 34
- Raw bytes: 5,033,994
- Silver file: `data/silver/20261101T091622Z_291e9d2a/candles.parquet`
- Gold folder: `data/gold/20261101T091622Z_291e9d2a/`
- DuckDB database: `data/gold/20261101T091622Z_291e9d2a/warehouse.duckdb`
- Query results: `evidence/query_daily_sample.csv`
- Measured chart: `evidence/overview.png`

Open data/current.json for the authoritative relative paths. The uncompressed database contains persisted tables, so it does not depend on an absolute path from the preparation machine. Read the source attribution before redistribution.

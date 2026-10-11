# BigQuery and dbt Platform follow-up

The local app and dbt/DuckDB path are implemented first. This milestone remains
separate: no cloud resources, credentials, uploads, or hosted jobs have been created.

To match the reference's hosted analytics path:

1. Choose gym-specific cloud project/datasets and private-data publication settings.
   Keep these separate from Dofus configuration. Add the BigQuery client and dbt
   BigQuery adapter only for this milestone and lock their versions with uv.
2. Reuse the validated read-only operational extract and content-addressed snapshot
   contract. Load raw tables with snapshot ID/extraction time; publish manifest last.
   Reject incompatible schema changes and make partial retries idempotent.
3. Configure a gym dbt Platform project with external credentials and isolated
   dev/prod targets; never commit credentials or publish the Obsidian vault.
4. Verify model parity and SQL adapter differences, especially decimal arithmetic,
   snapshot selection, date aggregation, and cross-adapter data tests.
5. Run hosted snapshot publication/dbt explicitly. Keep FastAPI recording on SQLite
   and available when analytics or cloud services fail.

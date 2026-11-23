# Manual SQL migrations

All schema changes are Alembic revisions in `backend/migrations/versions/`,
applied by the `migrate` compose service on deploy (`alembic upgrade head`).
A fresh database is built entirely by Alembic: revision 0001 creates the
baseline schema from `backend/migrations/sql/0001_baseline.sql`.

The one file here is deliberately kept out of the automatic chain:

`006_drop_fp32_embedding.sql` drops the unused full-precision `chunks.embedding`
column. It is destructive, so run it by hand once the release is stable and a
backup exists. It is a no-op on databases created from the current baseline,
which never had the column.

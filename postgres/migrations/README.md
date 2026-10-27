# Legacy SQL migrations

`001`–`004` are already applied to every existing database and are folded into
`postgres/init.sql` for fresh ones. New schema changes are Alembic revisions in
`backend/migrations/versions/`, applied by the `migrate` service on deploy
(`alembic upgrade head`).

`006_drop_fp32_embedding.sql` is destructive and deliberately manual; run it
once the release is stable and a backup exists.

# Phase 6: Unexpected application of certificates migration `0002` in the development database

Investigation only. Nothing was fixed, reversed, started, stopped, committed or changed in any database or project file.
Written 2026-10-19. All times are shown in IST (UTC+5:30) with UTC where the database reports it.

**Conclusion: root cause not established.** The evidence strongly supports that a `migrate` (equivalent here to
`migrate_schemas`) was typed in an interactive terminal on this PC at about 12:37:58 IST. It does not identify who typed it,
which terminal, or the exact command text. No evidence supports any automatic or background cause.

## 1. Incident summary

| Item | Verified fact | Source |
|---|---|---|
| What | `certificates.0002_alter_certificate_integrity_hash_idcardtoken` is applied in `public` and in all four tenants of `edusekai_db` (`greenvalley_demo`, `spsghy`, `sunrisevalley_school`, `test_chk`). | Read-only SQL, session verified read-only |
| When (UTC, then IST) | public 07:07:58.5 (12:37:58); greenvalley_demo 07:08:01.5; spsghy 07:08:04.3; sunrisevalley_school 07:08:06.7; test_chk 07:08:08.9 (12:38:08), then post-migrate seeding finished 07:08:10.0 (12:38:10). | `django_migrations.applied`, `roles_role.updated_at` |
| How many times | Exactly once per schema (one row per migration name per schema). | `group by name, count(*)` |
| Other migrations | None. Across all five schemas the only migration applied since 2026-10-18 is this one. | `django_migrations` |
| Effect on data | New tables exist in every tenant with the expected check constraint and 7 indexes; `integrity_hash` is `varchar(128)`. Certificate, token, settings and sequence tables: 0 rows, and **0 lifetime inserts, updates and deletes** in `pg_stat_user_tables`. | Read-only SQL |
| Side effects of the run | `roles_role` rows were re-saved right after each tenant's migration (5 per tenant in the window), which is the project's `post_migrate` seeding. No audit-log rows, no user logins and no JWT tokens issued in 07:00 to 07:20 UTC. | Read-only SQL |
| Current state | Still at `0002`. 0 other connections to the dev DB when checked. | Read-only SQL |

Not asserted: that "empty tables" means harmless. The migration also changed the shape of `integrity_hash` and created the
token table; those are schema changes whether or not rows exist. They match the forward SQL rehearsed earlier on a disposable
copy, so the schema is believed to be as designed, but that is expected behavior, not proof about the cause.

## 2. Environment and database identity (secrets redacted)

- Repository `D:\MAIN-GIT-CLONE-REPOS\ERP`, branch `main`, **201** `git status` entries before and after the investigation (identical; this report is the only change, making 202 once saved).
- `backend/.env` points at `DB_NAME=edusekai_db`, `DB_HOST=127.0.0.1`, `DB_PORT=5432` (a local PostgreSQL 18.4 server started 2026-10-15 19:28 UTC; user and password not printed). There are no other env files (`.env`, `.env.example` only).
- That server holds other databases unrelated to this project (`Mydb`, `mis_db`, `mocha_shoping`, `recruitmentdb`, `rms_db`, `school`, `postgres`) plus `edusekai_db` and `test_edusekai_db`. The development database is identified from the live connection (`current_database()` = `edusekai_db`), distinct from `test_edusekai_db`.
- Migration `0002` depends on `certificates.0001_initial`, `staff.0002_leavetype_...` and `students.0007_admissiondocument_...`; all were already applied. It is a pure add (widen one column, create one table); nothing else was pending in the chain.
- The file `0002...py` is dated 2026-10-17 13:42 (generated, not applied then); it stayed pending until 07:07:58 UTC on 2026-10-19.

## 3. What a plain `migrate` does in this project (important)

`django_tenants` is the first entry in `SHARED_APPS`, and its package ships `management/commands/migrate.py` containing
`Command = MigrateSchemasCommand` (read statically, not run). **Therefore `python manage.py migrate` is `migrate_schemas`**:
with no flags it migrates the shared schema and then every tenant, in order. That is exactly the observed pattern (public first, then each tenant about 2 to 3 seconds apart, seeding after each). It also means any ordinary `migrate` typed for another reason applies every pending migration, including a freshly generated one such as `0002`. Starting `runserver` additionally prints "You have N unapplied migration(s)" (Django's `check_migrations`), a common prompt to run `migrate`.

## 4. Read-only commands and queries used

All database inspection of the dev DB used one raw `psycopg2` connection with `set_session(readonly=True)`; the script asserted
`SHOW transaction_read_only = on` and **deliberately attempted a write that PostgreSQL rejected** (`ReadOnlySqlTransaction`)
before running anything else. Statements were SELECTs on: `pg_database`, `pg_stat_database`, `pg_stat_user_tables`,
`pg_stat_activity`, `pg_settings`, `information_schema`, `pg_indexes`, `pg_constraint`, each schema's `django_migrations`,
`roles_role`, `core_auditlog`, `accounts_user.last_login`, `token_blacklist_outstandingtoken`, and the certificates tables
(counts only). Script: `inv_readonly.py` in the session scratchpad. File-system and OS checks were listings and `grep` on
named files; PowerShell cmdlets used: `Get-CimInstance Win32_Process`, `Get-Process`, `Get-NetTCPConnection`,
`Get-ScheduledTask`, `Get-WinEvent`. No Django management command was run (none was needed; `migrate`-family commands can
execute startup hooks and writes, so none was used). `docker ps -a` was run in the earlier phase and failed because the daemon is not running.

## 5. Sources inspected and unavailable

| Source | Inspected? | Result and limitation |
|---|---|---|
| Dev DB migration rows, seeding timestamps, stats, activity | Yes | Gives exact times and the `migrate_schemas` signature; cannot name an actor. |
| PostgreSQL server log (`postgresql-2026-10-16_005859.log`) | Yes | Has no entry for 12:35 to 12:42 except autovacuum and a checkpoint. `log_statement = none`, `log_connections` not enabled, `log_min_duration_statement = -1`, so migrations are **not** logged. Not informative. |
| PowerShell history (`ConsoleHost_history.txt`) | Yes (masked excerpts) | No timestamps. Ends with repeated `cmd` entries; last written 12:36:55. Commands typed inside `cmd` windows are not recorded here. Shows a repeated routine (section 6). |
| Process tree and start times | Yes | See section 6; shows who started what, not what was typed. |
| VS Code logs for today (`20261019T123144`) | Yes | Restored persistent terminals at 12:31:48; a `cmd.exe` terminal launched at 12:31:52 with shell integration unavailable. VS Code does not log typed commands. |
| Claude Code transcripts for this project (4 days) | Yes (all local transcripts) | One transcript (this session). It contains no migrate command between 06:30 and 08:00 UTC before 07:18; my commands at 07:06:58 and 07:09:15 UTC bracket a gap of 2 min 17 s that contains the migration. |
| Codex local logs | Partly | No sessions folder found; its log database contains no migrate command text; process `codex.exe` started 12:35. Not conclusive either way. |
| Antigravity | Yes | Logs end in May 2026; not used today. |
| Scheduled tasks, git hooks, repo launchers, CI | Yes | Nothing matches (no `.github`, no pipeline files; only `docker-compose.yml` files; hooks directory has only samples). |
| Windows Security 4688 (process creation) | Yes | Not enabled/empty. |
| PowerShell script-block log (4104) | Yes | 4 events in 12:25 to 12:50, none in 12:36:30 to 12:39:30, none mention migrate. Not a complete record of commands. |
| Windows Prefetch | No | Access denied. |
| `cmd.exe` command history | No | Not persisted; not accessible. |

## 6. Evidence for and against each candidate

| Candidate | Classification | Evidence for | Evidence against / limits |
|---|---|---|---|
| **A. A manually typed `python manage.py migrate` (= `migrate_schemas`) in an interactive terminal on this PC** | **Strongly supported** | (1) DB signature is exactly `migrate_schemas` (shared then each tenant, seeding after each, single run). (2) In this project plain `migrate` is that command (section 3). (3) PowerShell history shows a repeated routine `python manage.py migrate` then `python manage.py runserver` (lines 3775/3776, 3794/3795, 3796/3797, 3799/3800 of 3815). (4) Interactive terminal activity right before: `cmd` entered at 12:36:55 (history's last write), cmd 11552 started 12:36:55 then `npm run dev` (frontend, port 3000) at 12:37:09; cmd 5172 started 12:37:10 then `npm run dev` (tenant frontend, port 3555) at 12:37:23; another `cmd` at 12:36:14. (5) Precedent: certificates `0001` was applied 2026-10-17 17:27:15 to 17:27:22 IST and the earlier process listing showed two `python manage.py runserver` processes starting at 17:27:35, 13 s later (the same migrate-then-runserver signature; those processes no longer exist, so this cannot be re-verified). (6) No automatic path exists (rows below). | No `runserver` or other Python process was alive after 12:38 (none at 12:40 and none now), whereas the routine in (3) would leave one running unless it was stopped or never started. The exact command, terminal and typist are not recorded anywhere I could read. |
| **B. That the person who typed it was you, doing the usual `migrate` before `runserver`** | **Plausible but unconfirmed** | Matches the habit in (3), the timing of the frontends starting 30 to 50 s earlier, and that `0002` was the only pending migration (so it would have applied "silently"). You report it was not intentional; a habitual `migrate` for a different purpose is consistent with that. | Cannot be tied to a person: the terminals are restored VS Code terminals and no log records keystrokes. |
| C. Claude Code in this session | **Unsupported** | My transcript has no migration command in the window; my 07:06:28 UTC probe still read `0001`; no gap-closing evidence for me. | A direct negative cannot be proven for other agents (rows D, E). |
| D. Another Claude session | **Unsupported** | Only one transcript exists for this project in 4 days. | Limited to what is stored locally. |
| E. Codex / other agent tools | **Unsupported (no evidence; coverage limited)** | `codex.exe` started 12:35 (a clue only). No migrate text in its log database; no sessions folder found. | I could not read all of Codex's data; absence of evidence here is weak. |
| F. Docker container entrypoint (`entrypoint.sh` runs `migrate_schemas` on start) | **Unsupported** | Docker daemon not running; no container evidence. | State at 12:37 itself cannot be reconstructed; not running now and no Docker process started that morning. |
| G. `runserver`, `next dev`, `npm run dev` | **Unsupported** | `runserver` only warns about pending migrations (Django `check_migrations`); `next dev` does not touch the database; no custom runner or startup hook (static search of non-test code found no `call_command`/`migrate(` use). | None. |
| H. Scheduled task, git hook, CI, seed command, tenant creation | **Unsupported** | None found; seed commands create new tenants only (`auto_create_schema`), which would not touch the five existing schemas. | None. |
| I. Process start times as proof | **Rejected as a method** | The two frontend dev servers starting 12:37:09 and 12:37:23 and `codex.exe` at 12:35 are timing clues only. | They do not run migrations. |

## 7. Confidence and remaining uncertainty

- High confidence in the **what and when** (database evidence, read-only verified).
- Moderate-to-high confidence that the **mechanism** was an interactive `migrate`/`migrate_schemas` on this machine.
- **Root cause (who typed what, where): not established.** Missing: terminal scrollback or history of the `cmd` shells, any PostgreSQL statement logging, process-creation auditing.
- The absence of a surviving `runserver` is unexplained and weakens, but does not disprove, the "migrate then runserver" reading.
- This analysis does not show the schema is wrong; the forward SQL was rehearsed earlier on a disposable copy and the live schema matches it.

## 8. Recommended preventive controls (proposals only, none implemented)

1. Turn on PostgreSQL attribution for the dev server: `log_connections`, `log_statement = 'ddl'` and a `log_line_prefix` with `%u %a %p`, plus a distinct `application_name` per tool. Needs a server config change (not made).
2. Run migrations only on request: agree that generated migrations stay unapplied until approved; mention in `CLAUDE.md`/team notes that **`python manage.py migrate` in this project migrates every tenant**, and prefer `migrate_schemas --shared` / `--schema=<name>` when targeting less.
3. Consider a separate database for assistant/test activity so the day-to-day dev DB is not the default target.
4. Add a guard to `migrate` in the dev environment (for example a prompt or an environment-variable allow-list) if accidental migrations matter.
5. Keep terminal history for `cmd` (use PowerShell or enable `doskey` logging) or record the command line in shell integration.
6. Do not reverse `0002`: its reverse drops the token table and widens/shrinks columns; the tables are empty today but a reverse is not a repair and would not explain the event.

## 9. Next actions needing your explicit approval (none taken)

1. Tell me whether you, or another tool you run (an IDE run configuration, a second agent), typed `migrate` around 12:37 IST on 2026-10-19; that would settle attribution with a human answer.
2. Decide whether the dev DB stays at `0002` (recommended: yes; it is the intended state) or is deliberately returned to `0001` through a reviewed, backed-up procedure.
3. Approve the logging changes in section 8 (item 1) if you want future events to be attributable.

## 10. Safety statement

- **Databases inspected:** `edusekai_db` (dev) with a verified read-only session; no connection to any other database on the server beyond listing database names; `test_edusekai_db` was not touched in this task.
- **Writes in this task:** none, to any database, schema, table or row. (Earlier, separately authorized phases did write to disposable copies and, with your approval, cleaned one stale schema in `test_edusekai_db`; those are documented in the decisions document, not here.)
- **Git:** 201 entries before and after; no change except adding this file.
- **Not done:** no migrate/makemigrations/sqlmigrate against any database, no rollback, no process started or stopped, no code, env or Git configuration changed, no secrets printed.

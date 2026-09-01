# CI Root Cause Analysis — RelayHub

Method: since raw logs were unreachable (see `CI_FAILURE_INVENTORY.md`), each job's exact CI command was reproduced directly — locally against the repo's actual dependency manifests (backend against real PostgreSQL 16 + Redis, matching CI's service containers), and for the two jobs the sandbox itself couldn't run (Maven/Java, Docker), via a real GitHub Actions run on a throwaway branch (see `CI_FIXES_APPLIED.md`).

| Root Cause Group | Runs Affected | Current Main | Reproducible | Fix Required | Status |
|---|---:|---|---|---|---|
| backend — sqlite tests | 101 | Passing (402/402) | No (passes cleanly, 3x in a row) | No | HISTORICAL — ALREADY FIXED |
| frontend — Typecheck | 45 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend-postgres — Tests | 37 | Passing (402/402 vs real Postgres+Redis) | No | No | HISTORICAL — ALREADY FIXED |
| backend — Lint (ruff) | 26 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend-postgres — alembic migrations | 25 | Passing (clean upgrade head) | No | No | HISTORICAL — ALREADY FIXED |
| java-sdk — mvn compile test | 19 | Passing (confirmed on GitHub's real runner, both before and after this audit's change) | No | No | HISTORICAL — ALREADY FIXED |
| python-sdk — pytest | 16 | Passing (24/24) | No | No | HISTORICAL — ALREADY FIXED |
| node-sdk — npm build | 16 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| go-sdk — go build | 16 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| cli — tsc | 12 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend — Typecheck (mypy) | 5 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| docker-build — validate compose | 3 | Passing (confirmed on real runner) | No | No | HISTORICAL — ALREADY FIXED |
| python-sdk — mypy | 1 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| go-sdk — go test | 1 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| Instant whole-run failure (6-7 jobs failing together in <3s, no step reached) | 10 runs | Not observed on current main | Not reproducible (pattern doesn't recur; can't force a GitHub-side incident) | Unknown | **UNRESOLVED — CANNOT BE CONCLUSIVELY DETERMINED.** Every failed job in this group errored before its first step began, across every job type simultaneously, in two tight bursts (5 runs in ~4 min on Aug 22, 5 more in ~4 min on Aug 30) that line up with rapid successive commits. Check-run annotations were empty and raw logs unreachable. `.github/workflows/ci.yml` was not changed in either window. Most consistent with a transient GitHub Actions infrastructure hiccup or a runner-provisioning issue during rapid concurrent pushes — but this is a plausible explanation, not a confirmed one, and is reported as such rather than asserted. |

## Note on the java-sdk investigation specifically

During this audit, `mvn -B compile test` failed locally with `central-publishing-maven-plugin` unresolved (declared as an unconditional `<extensions>true</extensions>` build extension, which Maven must resolve while reading the POM before any goal runs). This looked like a strong candidate for the 19 historical `java-sdk` failures.

It was not verifiable locally because the sandbox this audit ran in cannot reach `repo.maven.apache.org` at all (confirmed via `x-deny-reason: host_not_allowed` — this blocks *any* Maven Central request, not just this one artifact). Rather than assume, a fix (moving publish-only plugins into an opt-in `release` profile) was pushed to a branch and verified through a real PR-triggered CI run on GitHub's own runner.

Result: **the unmodified `main` commit already passed `java-sdk` cleanly on GitHub's real runner**, both before and after the fix. So this was not, in fact, a live bug — Maven Central is reachable from GitHub's runners even though it wasn't from the sandbox. The fix was still merged (it's a correct hygiene improvement with zero observed regression, verified by the same green run), but it is not the explanation for the 19 historical failures, which — like every other group above — were resolved by earlier commits before this audit began.

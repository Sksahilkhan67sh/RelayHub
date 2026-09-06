# CI Fixes Applied — RelayHub

## Summary

Current `main` was already fully green (all 9 CI jobs passing) before this audit began — confirmed by pulling the run for the pre-audit HEAD commit (`a9b3975`, run `33381633634`, conclusion `success`, all 9 jobs `success`). All 205 historical failures except one 10-run cluster were confirmed, via direct reproduction, to be resolved by commits made during the original 3-week development window — not by anything changed in this audit.

**One change was made and merged, but it turned out not to be fixing a live bug** (see below and `CI_ROOT_CAUSE_ANALYSIS.md`).

## Change made

**File:** `sdks/java/pom.xml`
**Branch:** `fix/java-sdk-publish-plugins-profile`
**PR:** [#1](https://github.com/Sksahilkhan67sh/RelayHub/pull/1) — merged via regular merge commit (no squash, no history rewrite)
**Merge commit:** `98839acbedfce204e3bd82455d75de14482cf187`

Moved the publish-only plugins (`maven-source-plugin`, `maven-javadoc-plugin`, `maven-gpg-plugin`, `central-publishing-maven-plugin`) out of the unconditional `<build><plugins>` block and into an opt-in `release` Maven profile. `central-publishing-maven-plugin` in particular was declared with `<extensions>true</extensions>`, which forces Maven to resolve it while reading the POM, before any goal executes — so it was requiring a publish-only artifact to resolve even for a plain `mvn compile test`. Publishing now requires `mvn -Prelease clean deploy` explicitly; a normal CI build no longer touches any of it.

**Why this was pushed via PR instead of straight to main:** the sandbox this audit ran in cannot reach `repo.maven.apache.org` at all (`x-deny-reason: host_not_allowed`), so nothing about the Java build could be verified locally — not even a completely unmodified `mvn compile test`. The fix was pushed to a branch, and GitHub's own runner (which does have Maven Central access) ran the real CI workflow against it before it was merged.

**Verified result:** all 9 jobs passed on the PR's CI run (run `33419403082`), including `java-sdk` and `docker-build` (also otherwise unverifiable locally — no Docker daemon in the sandbox). Only after that real green run was the PR merged.

**Correction:** checking the commit immediately before this fix showed it *also* passed `java-sdk` cleanly on GitHub's real runner. So the extension-resolution issue was real in this audit's own sandbox, but not on GitHub's actual infrastructure — meaning this change fixes a legitimate build-hygiene issue with zero observed regression, but was not the cause of any of the 19 historical `java-sdk` failures, which were already resolved before this audit started.

## Changes explicitly not made

- No test was weakened, skipped, or given `continue-on-error`.
- No job was disabled.
- No historical commit was rewritten; no force-push occurred.
- No fix was applied to the "instant whole-run failure" cluster (10 runs) — its cause could not be conclusively determined (see `CI_ROOT_CAUSE_ANALYSIS.md`), so nothing was changed based on a guess.

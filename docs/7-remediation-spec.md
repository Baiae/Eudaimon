# Eudaimon Execution-Safety Remediation Specification

**Status:** Working remediation specification
**Scope:** Local reference implementation at `/Users/projectphaedra/Documents/ChatGPT/Eudaimon`
**Authority:** This document authorizes the ordered remediation work discussed with the user. It does not authorize Git commits, pushes, publication, deployment, destructive cleanup, or changes to the research design.

## 1. Objective

Correct the confirmed execution-safety and evidence-integrity defects in the reference engine while preserving its design-first, stdlib-only character. Each defect is a separate change unit with its own tests and verification gate. Do not combine unrelated repairs.

The engine remains a bounded reference implementation. These repairs do not turn it into a secure sandbox, validated scientific evaluator, or production autonomous research system.

## 2. Operating constraints

- Preserve existing project files and campaign data.
- Make one remediation at a time.
- Before each change, inspect the exact current implementation and relevant tests.
- Add regression tests that fail against the defective behavior.
- Run the complete unit-test suite after each change.
- Do not run a real campaign as part of adversarial tests unless explicitly needed and separately approved.
- Use temporary directories for hostile-input and failure-injection tests.
- Do not commit, push, merge, reset, clean, install dependencies, or publish.
- Keep the implementation standard-library-only unless a separate design decision approves otherwise.
- Fail closed when ownership, path identity, candidate identity, or transaction state cannot be established.

## 3. Remediation order and acceptance criteria

### R1 — Exclusive run lock and ownership-safe release (P1)

**Defect:** The current lock is created through a temporary file followed by `os.replace`, which overwrites an existing lock. Release unconditionally unlinks the path.

**Required behavior:**
1. Create the lock atomically with exclusive-create semantics (`O_CREAT | O_EXCL`).
2. If a lock already exists, refuse acquisition without changing its bytes or inode.
3. Write the run identifier and durable lock metadata before reporting acquisition success.
4. If writing the newly created lock fails, remove only the lock inode created by that acquisition.
5. Release only when the lock content identifies the current run as owner.
6. If the lock is missing, malformed, or owned by another run, do not remove it; report a controlled ownership error.
7. Do not automatically reclaim stale locks. Stale-lock recovery is a separate explicit operator procedure.

**Tests:** competing acquisition is refused; existing lock content is unchanged; non-owner release preserves the lock; owner release removes it; failed initialization does not leave an orphan lock; engine still releases its own lock on normal and handled-error paths.

### R2 — Campaign path containment and symlink rejection (P1)

**Defect:** Paths are resolved before symlink checks, and configured target paths are not constrained to the campaign root.

**Required behavior:**
1. Preserve configured path values before resolution.
2. Reject absolute target paths and traversal outside the campaign.
3. Reject symlinks in every path component used for the campaign target, evaluator, and proposal directory.
4. Resolve paths and verify they remain beneath the resolved campaign root.
5. Require target and evaluator to be regular files and proposal directory to be a real directory.
6. Revalidate candidate paths immediately before evaluation to reduce path-substitution risk.
7. Document that path checks alone do not defend against a hostile process racing filesystem changes; stronger isolation remains separate work.

**Tests:** reject target symlink, evaluator symlink, symlinked proposal directory, `../` escape, absolute target, and candidate symlink; accept ordinary in-campaign files.

### R3 — Immutable evaluation snapshot and digest binding (P1)

**Defect:** The engine hashes the candidate after evaluator execution, allowing the recorded digest to describe different bytes from those actually evaluated.

**Required behavior:**
1. Read candidate bytes once and create a private immutable-by-convention snapshot in an engine-controlled temporary location.
2. Compute SHA-256 and byte count from the snapshot before evaluation.
3. Pass only the snapshot path to the evaluator.
4. Record the pre-evaluation snapshot digest and byte count as authoritative evidence.
5. Ensure evaluator-side mutation cannot alter the original proposal or the bytes represented by the recorded digest.
6. Clean up the snapshot in a `finally` path.
7. If the snapshot cannot be safely created or evaluated, fail closed.

**Tests:** evaluator that mutates its input cannot change the recorded digest; original proposal remains unchanged; digest matches bytes read by evaluator; snapshot is removed after success and failure.

### R4 — Recoverable promotion/evidence transaction (P1)

**Defect:** Target promotion occurs before ledger and state writes. A crash can leave promoted content without a corresponding durable decision record. Initial state-write failure can also strand the lock.

**Required behavior:**
1. Define explicit transaction phases and stable transaction identifiers.
2. Persist a promotion-intent record containing old-target and candidate digests before replacing the target.
3. Promote using a same-directory temporary file, fsync file data, atomic replace, and fsync the containing directory where supported.
4. Persist a commit record only after verifying the promoted target digest.
5. On startup, inspect incomplete transactions before evaluating new proposals.
6. Reconcile only when the recorded intent and current target digest provide an unambiguous safe outcome; otherwise halt for operator review without overwriting data.
7. Place all post-acquisition initialization inside the lock-release `try/finally` boundary.
8. Never infer successful promotion solely from a state file.

**Tests:** inject failures before promotion, after promotion, before commit, and during state update; prove restart either safely reconciles or halts without losing the prior target or fabricating a commit.

### R5 — Evaluator process containment and resource controls (P1 / declared limitation)

**Defect:** Evaluator runs with the current user's permissions; timeout does not reliably terminate descendants; output is unbounded; no memory or filesystem isolation exists.

**Required behavior:**
1. Establish a bounded output strategy that cannot buffer arbitrary stdout/stderr in memory.
2. Terminate the evaluator process group on timeout and verify termination.
3. Apply supported resource limits where portable and reliable; record any limits that cannot be enforced on macOS.
4. Restrict evaluator working paths to the campaign and snapshot inputs where feasible.
5. Explicitly distinguish process management from a true security sandbox.
6. If adequate containment cannot be guaranteed on the supported platform, keep untrusted evaluators unsupported and document the limitation rather than claiming isolation.

**Tests:** timeout terminates child processes; oversized output is bounded and causes a controlled failure; resource-limit behavior is tested where supported; documented unsupported isolation is explicit.

### R6 — Adversarial and failure-injection coverage (P1/P2)

Add direct tests for the engine, evaluator protocol, policy behavior, path boundaries, lock ownership, candidate immutability, transaction recovery, malformed output, timeout, output limits, and ledger/state failures. Tests must be deterministic and use temporary fixtures. No network, model downloads, or third-party dependencies.

### R7 — Evidence ledger integrity (P2)

Evaluate append-only event sequencing, event schema/versioning, hash chaining, partial-line recovery, and tamper detection. Any ledger format change requires a documented migration/compatibility decision. Do not silently rewrite existing campaign evidence.

### R8 — Repository hygiene and documentation (P2)

Review proposal tracking and runtime-evidence retention deliberately. Current ignore rules exclude all proposal files and `.autoresearch/`; decide whether proposals are source artifacts and whether runtime state is reproducible, local-only, or exportable. Correct README layout numbering and align claims with actual tests. Do not change ignore rules until retention semantics are explicitly settled.

### R9 — Local/public repository reconciliation (P2)

The local directory currently has an unborn `master` branch, no commits, and no remote; the public GitHub repository has a separate one-commit `main` history and a different layout. Do not merge or overwrite either history. First produce a content-level inventory and proposed canonical layout. Any remote configuration, history creation, or push requires a separate explicit confirmation.

## 4. Completion gates

A remediation item is complete only when:
- the defect is corrected in code;
- a regression test demonstrates the prior failure is prevented;
- the full local test suite passes;
- relevant source and test diffs are reviewed;
- no unrelated files or campaign artifacts changed; and
- the result and remaining limitations are reported.

## 5. Current execution boundary

**R1–R4 are complete. R5 has bounded process/output controls and an enforced local evaluator integrity pin, but is not a sandbox (no memory or filesystem confinement). R6 transaction, state, and ledger fault-injection closure for this milestone is verified; its wider resource-failure research remains open. R7 has strengthened read-only structural validation, not authenticated tamper detection or a v2 writer. R8–R9 publication/migration decisions remain separate and unauthorized.** No real campaign, Git operation, or production/unattended execution is authorized.

## 6. Implementation log

### R1 — COMPLETE

- Replaced temporary-file-plus-replace locking with atomic `O_CREAT | O_EXCL` creation.
- Lock acquisition now fails closed when a lock already exists and preserves the existing lock.
- Release verifies the run identifier, regular-file type, and original device/inode before unlinking.
- Failed lock initialization removes only the inode created by that acquisition.
- Stale locks are intentionally not reclaimed automatically.
- Added regression coverage for competing acquisition, unchanged existing lock, non-owner release, owner release, failed initialization, malformed lock preservation, inode replacement, and lock release after a handled evaluator error.
- Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` — **9 tests passed**.
- No campaign was executed for this remediation. No Git operation was performed.

**Remaining boundary:** this is cooperative process locking. It is not a defense against a malicious process with permission to manipulate the campaign directory, and stale-lock recovery remains an operator decision.


### R2 — COMPLETE

- Preserved the configured target as a campaign-relative lexical path rather than resolving it before inspection.
- Rejected absolute target paths and any target containing parent-directory traversal.
- Added component-by-component `lstat` validation for target, evaluator, and proposals directory paths.
- Rejects symlinks in intermediate directories and final path components; checks expected regular-file/directory types.
- Revalidates proposal directory and candidate path immediately before evaluator invocation.
- Evaluator now receives the validated lexical candidate path rather than a resolved path that could silently follow a symlink.
- Added regression tests for normal paths, target symlink, intermediate target-directory symlink, evaluator symlink, proposals-directory symlink, traversal, absolute target, and candidate symlink.
- Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` — **17 tests passed**.
- Read-only validation against the actual `campaigns/rr_engine` directory — **PASS**. No evaluator or campaign run was started.
- No Git operation was performed.

**Remaining boundary:** these checks reduce accidental and straightforward symlink/path escapes, but they do not eliminate time-of-check/time-of-use races if another process can modify the campaign tree concurrently. The engine is still not a security sandbox.


### R3 — COMPLETE

- Added an engine-created candidate snapshot in the system temporary directory.
- Candidate bytes are streamed once into the snapshot while SHA-256 and byte count are computed from those exact bytes.
- Candidate opening uses `O_NOFOLLOW` where supported and verifies the opened descriptor is a regular file.
- Snapshot is flushed, fsynced, and changed to read-only mode before evaluator invocation.
- Evaluator receives only the snapshot path; evidence fields are taken from the pre-evaluation snapshot digest and byte count, not from a post-evaluation read of the mutable proposal.
- Snapshot is removed in a `finally` path after success, evaluator failure, or timeout.
- Added regression tests proving evaluator-read bytes match the recorded digest, ordinary evaluator writes are blocked, the original proposal remains unchanged, and snapshots are removed after both success and failure.
- Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` — **19 tests passed**.
- No campaign was executed. No Git operation was performed.

**Remaining boundary:** read-only file permissions and private temporary-file creation provide cooperative protection, not a security boundary. An evaluator running as the same user may attempt to change permissions or otherwise manipulate accessible files. R5 must address process containment and clearly state what macOS can and cannot enforce.


### R4 — COMPLETE

- Added durable promotion_intent records with unique transaction IDs, run IDs, and old-target/candidate SHA-256 digests before any target replacement.
- Promotion now copies the candidate into a same-directory temporary file while hashing the exact copied bytes; it refuses promotion if the proposal no longer matches the evaluated snapshot digest.
- Before replacement, the incumbent target is rehashed and must still match the digest captured in the intent.
- Promotion flushes and fsyncs the temporary file, atomically replaces the target, fsyncs the containing directory where supported, and verifies the resulting target digest.
- Added durable promotion_commit records only after post-replacement digest verification.
- Startup recovery scans the ledger for unmatched promotion intents before any new evaluation. If the target matches the candidate digest it records a recovered commit; if it matches the old digest it records a recovered abort. Equal digests, malformed/ambiguous ledger content, or a target matching neither digest stop execution for operator review without modifying the target.
- Moved all post-lock-acquisition initialization, including initial state persistence and transaction recovery, inside the lock-release try/finally.
- Added failure-injection coverage for failure before replacement, crash after replacement but before commit, initial state-write failure, post-commit state-write failure, candidate mutation after evaluation, and ambiguous recovery states.
- Verification: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v — **28 tests passed**.
- Tests use temporary campaign directories. No real campaign was executed. No Git operation was performed.

**Remaining boundary:** recovery is ledger-driven and digest-based, but it does not provide protection against a hostile same-user process racing filesystem operations. Directory fsync is attempted and tolerated when the platform/filesystem does not support it. Partial or malformed ledger records fail closed; comprehensive ledger integrity and partial-line policy remain in R7.

### R5 — PARTIALLY IMPLEMENTED (process/output bounds)

- Evaluator stdout/stderr are redirected to temporary files, not captured in unbounded memory.
- On macOS/POSIX, evaluator file output is limited to 64 KiB per stream with RLIMIT_FSIZE; reaching the limit fails evaluation closed.
- The evaluator runs in a separate process session; timeout sends SIGKILL to its process group and waits for the direct child. The group is also killed on normal completion to avoid leaving background descendants.
- Added regression tests for oversized stdout, oversized stderr, and a timed-out evaluator with a descendant. The full local suite passes: **31 tests**.
- **Not a security sandbox:** a same-user evaluator can access or modify accessible filesystem resources, network services, and other processes. RLIMIT_FSIZE limits regular-file writes by the evaluator, but does not provide filesystem confinement. Memory limits and filesystem isolation remain unimplemented. No untrusted evaluator is authorized.
- No real campaign was run. No Git operations were performed.

### R6 — EXPANDED, NOT COMPLETE

- Added deterministic adversarial protocol tests for malformed JSON, non-finite score, missing Protect Gate, nonzero evaluator exit, and empty stdout. These use temporary campaigns only.
- Combined with R1–R5 tests, the local suite now has 39 passing tests. Remaining R6 work includes more systematic resource-failure and state/ledger fault injection.

### R7 — STRUCTURAL AUDIT ADDED, CRYPTOGRAPHIC INTEGRITY UNRESOLVED

- Added stdlib-only, read-only `tools/audit_ledger.py` and three tests. It checks JSONL framing, event shape, duplicate/unmatched transaction IDs, and pending intents without rewriting evidence.
- Existing campaign ledger inspected read-only: 24 records, zero pending transactions, zero structural issues.
- **This is not tamper detection:** the legacy ledger lacks hash chaining, sequence numbers, and authenticated provenance. Historical records cannot retroactively be authenticated. Schema/version and migration policy require explicit review before modifying the writer.
- No real campaign executed; no Git operations performed.

### R8–R9 — RECONCILIATION PROPOSAL WRITTEN, NOT EXECUTED

- Added `docs/8-evidence-and-repository-decisions.md` with proposed ledger v2 migration boundaries, retention choices, and path-level local/public inventory.
- Public GitHub `Baiae/Eudaimon` main was checked read-only at `9c464796a68ca19e565c7bdd5f764691a78616a4`. Local Git remains an unborn `master` without a remote.
- No hash-chain migration, ignore-rule change, Git history operation, or publication has occurred. Content-level semantic comparison and human approval remain required.

### R6/R7/R9 — ADDITIONAL VERIFICATION

- Added two read-only ledger auditor regression tests (duplicate intent and malformed JSON) and two fault-injection tests (ledger write failure, malformed ledger recovery). The complete test suite now passes **43 tests**.
- Fetched the nine corresponding public files at immutable commit `9c464796a68ca19e565c7bdd5f764691a78616a4` and compared their SHA-256 digests to the local versions. All nine differ; see `docs/8-evidence-and-repository-decisions.md` for byte-count evidence and the revised publication blocker.
- Public design documentation is substantially longer than local copies. No automated replacement, migration, or merge is appropriate without semantic reconciliation.
- No real campaign was executed; no Git commits, remotes, or pushes were created.

### 2026-11-17 — TARGETED SAFETY-HARDENING MILESTONE VERIFIED

**Scope of this milestone:** enforce the default evaluator trust restriction; close identified transaction/state fault-injection gaps; strengthen the *legacy* ledger structural audit. These are reference-engine safeguards, not a claim that R5–R9 or the public architecture are wholly implemented.

- **Evaluator trust restriction:** the CLI fails closed unless eval_runner.py matches the SHA-256 digest of the reviewed bundled example. Its campaign-local dependency rr_policy.py is separately SHA-256-pinned. Checks run before state/lock creation and immediately before each evaluator spawn. Programmatic EngineConfig.trusted_evaluator_sha256 exists for explicitly reviewed caller-supplied code (including ephemeral test fixtures), **not** as an unrestricted CLI flag. A changed adapter, changed imported policy, missing dependency, or invalid pin refuses execution.
- **Failure injection:** tests now cover intent append failure; torn intent and torn commit ledger lines; target replacement failure; failure after atomic target replacement and before committing; commit append failure; failed commit/abort recovery writes; initial, post-baseline, post-candidate, and post-commit state writes; atomic state replace failure; transaction-ID replay after completion; and mismatched committed digest. Tests assert target, ledger, lock, and restart behavior using temporary fixture campaigns only.
- **Ledger structural audit:** tools/audit_ledger.py now detects invalid/duplicate JSON keys, non-finite or invalid evaluation scores, missing required event fields, unrecognized legacy event kinds, malformed SHA-256 fields, duplicate/reused transaction IDs, orphan/repeated outcomes, outcome-run/digest mismatch, promoted-candidate linkage, incomplete trailing lines and pending intents. It **never** rewrites evidence. Recovery adds fail-closed checks for torn final lines, duplicate JSON members, non-finite JSON, unknown events, outcome-run mismatch, and outcome digest mismatch.
- **Verification:** PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -q — **76 tests passed**. Read-only audit of existing legacy evidence: **24 records, 0 pending transactions, 0 reported structural issues**, with unchanged bytes. No real campaign execution, Git commit, push, remote configuration, cleanup, install, or publication performed.

**Explicit remaining limitations:** This is **not a true sandbox**. The evaluator retains same-user filesystem/network/process access; memory isolation is not established; filesystem/pathname checks are still vulnerable to malicious concurrent substitution, and the programmatic pin override does not confer independent trust. A SHA-256 pin detects changes relative to a chosen trusted value, but is not a code signature or provenance proof. The legacy ledger has no authenticated origin, hash chain, external anchor, or signatures, so structural validity cannot establish historical authenticity or detect coherent adversarial rewrites. Ledger v2/migration, broader R5 isolation, remaining design choices D2–D4 and R8–R9 publication/reconciliation remain separate stop/go decisions.

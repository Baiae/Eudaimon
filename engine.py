#!/usr/bin/env python3
# AutoResearch-W reference sketch. UNTESTED. Stdlib only. Design intent, not measured behavior.
# Usage: python engine.py <campaign_dir>
#
# Setup (manual): git init in campaign dir; commit rr_policy.py, eval_runner.py, program.md;
#   .gitignore lists results.tsv, .engine/, AUDIT.md, PROPOSALS.md, ESCALATION.md;
#   chmod 444 eval_runner.py and program.md. Keep this engine OUTSIDE the campaign dir.
#
# Omitted (see docs/3, docs/5, docs/6): encrypted hidden fixtures, RSS watchdog,
#   process-group kill, Audit, baseline re-check schedule, Protect urgency override,
#   PROPOSALS handling, confirmation split, ledger prefix hash, Verifier script, hysteresis.

import hashlib, json, math, os, pathlib, re, shutil, subprocess, sys, tempfile, time, datetime

C = pathlib.Path(sys.argv[1]).resolve()
ENGINE_DIR = C / ".engine"
TARGET = "rr_policy.py"
EPOCH = 1
TRIAL_CAP, EVAL_TIMEOUT, HARNESS_TIMEOUT = 150, 300, 600
HARNESS_CMD = os.environ.get("HARNESS_CMD", "my-agent-cli --non-interactive").split()
COLS = ["trial", "epoch", "timestamp", "commit", "predicted", "score", "status", "reason",
        "hypothesis", "urgency_mode", "P1", "P2", "P3", "P4", "pred_error", "diff_lines",
        "tags", "salience_note", "gaming_note", "fail_counts", "runtime_s", "eval_hash"]

# ---------- helpers ----------
def now(): return datetime.datetime.now().isoformat(timespec="seconds")
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:12]
def git(*a): return subprocess.run(["git", *a], cwd=C, text=True, capture_output=True).stdout.strip()
def git_status(): return subprocess.run(["git", "status", "--porcelain"], cwd=C, text=True,
                                        capture_output=True).stdout.splitlines()
def nonblank(): return sum(1 for l in (C / TARGET).read_text().splitlines() if l.strip())
def reset(): git("reset", "--hard", "HEAD"); git("clean", "-fd")
def esc(v): return "-" if v is None else str(v).replace("\t", " ").replace("\n", " ")[:400]
def row(**kw):
    d = {c: "-" for c in COLS}; d.update(epoch=EPOCH, timestamp=now()); d.update(kw); return d

# ---------- ledger and state ----------
def ledger_append(r):
    p = C / "results.tsv"
    if not p.exists(): p.write_text("\t".join(COLS) + "\n")
    with p.open("a") as f: f.write("\t".join(esc(r[c]) for c in COLS) + "\n")

def read_rows():
    p = C / "results.tsv"
    if not p.exists(): return []
    lines = p.read_text().splitlines()
    rows = [dict(zip(COLS, l.split("\t"))) for l in lines[1:]]
    return [r for r in rows if r["status"] != "BASELINE"]

def load_state():
    p = ENGINE_DIR / "state.json"
    return json.loads(p.read_text()) if p.exists() else \
        {"trial": 0, "best": None, "eps": None, "best_size": None, "best_commit": None}

def save_state(st):
    ENGINE_DIR.mkdir(exist_ok=True)
    (ENGINE_DIR / "state.json").write_text(json.dumps(st, indent=1))

def streak(rows, pred):
    n = 0
    for r in reversed(rows):
        if not pred(r["status"]): break
        n += 1
    return n

def mode_of(rows):
    if streak(rows, lambda s: s == "FAILED") >= 3: return "survive"
    if streak(rows, lambda s: s != "KEEP") >= 10: return "thrive"
    return "excel"

# ---------- eval (gate + score) in a scratch copy ----------
def run_eval():
    scratch = pathlib.Path(tempfile.mkdtemp())
    shutil.copy(C / TARGET, scratch / TARGET)
    shutil.copy(C / "eval_runner.py", scratch / "eval_runner.py")
    # Hidden fixtures would be decrypted into scratch here (docs/5, section 5.5).
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "eval_runner.py", "--target", TARGET, "--epoch", str(EPOCH)],
                           cwd=scratch, text=True, capture_output=True, timeout=EVAL_TIMEOUT,
                           env={"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
                                "PATH": os.environ["PATH"]})
        lines = r.stdout.strip().splitlines()
        out = json.loads(lines[-1]) if lines else {}
        out["code"] = r.returncode
    except subprocess.TimeoutExpired:
        out = {"code": 124}
    except (json.JSONDecodeError, ValueError):
        out = {"code": 3}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return out, round(time.time() - t0, 1)

# ---------- guard (git-level checks only) ----------
def guard(head0, ev0):
    if git("rev-parse", "HEAD") != head0: return "history_rewritten"
    if any(l[3:] != TARGET for l in git_status()): return "out_of_scope_write"
    if sha(C / "eval_runner.py") != ev0: return "evaluator_edit"
    return None

# ---------- harness ----------
def prompt_for(mode, rows):
    tail = "\n".join("\t".join(r[c] for c in COLS) for r in rows[-10:])
    return (f"{(C / 'program.md').read_text()}\n\nMODE: {mode}\n\nLEDGER TAIL (last 10):\n{tail}\n\n"
            f"Propose one hypothesis, predict S, edit only {TARGET}, and output the JSON block.")

def harness(prompt):
    r = subprocess.run(HARNESS_CMD, input=prompt, cwd=C, text=True, capture_output=True,
                       timeout=HARNESS_TIMEOUT)
    out = json.loads(re.findall(r"```json\s*(\{.*?\})\s*```", r.stdout, re.S)[-1])
    if not 0.0 <= float(out["predicted_S"]) <= 1.0: raise ValueError("predicted_S out of range")
    return out

# ---------- ratchet ----------
def keep(st, t, hyp):
    git("add", TARGET)
    git("-c", "user.name=engine", "-c", "user.email=engine@local", "commit", "-m", f"trial {t}: {hyp}")
    st["best_size"] = nonblank()
    st["best_commit"] = git("rev-parse", "--short", "HEAD")

def baseline(st):
    runs = []
    for _ in range(3):
        out, _ = run_eval()
        if out.get("code") != 0: raise SystemExit(f"baseline failed: {out}")
        runs.append(out["S"])
    st.update(best=round(sum(runs) / 3, 9), eps=round(max(runs) - min(runs), 9),
              best_size=nonblank(), best_commit=git("rev-parse", "--short", "HEAD"))
    ledger_append(row(trial=0, commit=st["best_commit"], score=st["best"], status="BASELINE"))

# ---------- one trial ----------
def halt(cause):
    rows = read_rows()[-10:]
    tail = "\n".join("\t".join(r[c] for c in COLS) for r in rows)
    (C / "ESCALATION.md").write_text(f"# HALT\ncause: {cause}\nHEAD: {git('rev-parse', 'HEAD')}\n\n{tail}\n")
    raise SystemExit(f"halted: {cause}")

def trial(st):
    st["trial"] += 1; t = st["trial"]; save_state(st)
    rows = read_rows(); mode = mode_of(rows)
    head0, ev0 = git("rev-parse", "HEAD"), sha(C / "eval_runner.py")

    try:
        out = harness(prompt_for(mode, rows))
    except subprocess.TimeoutExpired:
        reset(); ledger_append(row(trial=t, status="FAILED", reason="timeout", urgency_mode=mode))
        return True
    except Exception:
        reset(); ledger_append(row(trial=t, status="DISCARD", reason="no_edit", urgency_mode=mode))
        return True

    hyp = out.get("hypothesis", "")
    base = dict(trial=t, predicted=out["predicted_S"], hypothesis=hyp, urgency_mode=mode,
                tags=",".join(out.get("tags", [])), salience_note=out.get("salience_note", ""),
                gaming_note=out.get("gaming_note", ""))
    ENGINE_DIR.mkdir(exist_ok=True)
    (ENGINE_DIR / "pending.json").write_text(json.dumps({"trial": t, "predicted": out["predicted_S"]}))

    breach = guard(head0, ev0)
    if breach:
        reset(); ledger_append(row(**base, status="FAILED", reason="guard_breach")); halt(breach)

    res, rt = run_eval()
    code = res.get("code")
    fail = {0: None, 2: "gate_fail", 3: "exception", 4: "nan", 124: "timeout"}.get(code, "exception")
    if fail is None and (res.get("S") is None or math.isnan(res["S"])): fail = "nan"
    if fail:
        reset(); ledger_append(row(**base, status="FAILED", reason=fail, runtime_s=rt))
        (ENGINE_DIR / "pending.json").unlink(missing_ok=True)
        return True

    S, P = round(res["S"], 9), res.get("P", {})
    d, size = round(S - st["best"], 9), nonblank()
    if d > st["eps"]:
        status, reason = "KEEP", "strict_improve"
    elif abs(d) <= st["eps"] and size < st["best_size"]:
        status, reason = "KEEP", "band_smaller"
    else:
        status, reason = "DISCARD", "no_improve"

    fields = dict(base, score=S, status=status, reason=reason, runtime_s=rt,
                  P1=P.get("P1"), P2=P.get("P2"), P3=P.get("P3"), P4=P.get("P4"),
                  pred_error=round(S - out["predicted_S"], 6), diff_lines=size,
                  fail_counts=json.dumps(res.get("fail_counts", {})), eval_hash=res.get("eval_hash"))
    if status == "KEEP":
        if reason == "strict_improve": st["best"] = S
        keep(st, t, hyp); fields["commit"] = st["best_commit"]
    else:
        reset()
    ledger_append(row(**fields))
    (ENGINE_DIR / "pending.json").unlink(missing_ok=True)

    rows = read_rows()
    if streak(rows, lambda s: s == "FAILED") >= 5: halt("5 consecutive FAILED")
    if sum(r["reason"] == "gate_fail" for r in rows[-10:]) >= 3: halt("3 Protect violations in last 10")
    return streak(rows, lambda s: s != "KEEP") < 20      # plateau ends the campaign

# ---------- main ----------
def main():
    if (C / "ESCALATION.md").exists(): raise SystemExit("halted: delete ESCALATION.md to resume")
    st = load_state()
    pend = ENGINE_DIR / "pending.json"
    if pend.exists():                                      # crash recovery
        reset()
        ledger_append(row(trial=json.loads(pend.read_text())["trial"], status="FAILED", reason="crash_recovery"))
        pend.unlink()
    if st["best"] is None:
        baseline(st); save_state(st)
    while st["trial"] < TRIAL_CAP and trial(st):
        save_state(st)
    save_state(st)
    print(json.dumps({"best": st["best"], "best_commit": st["best_commit"], "trials": st["trial"]}))

if __name__ == "__main__":
    main()

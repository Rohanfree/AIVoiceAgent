---
name: modify-code
description: Modify code in the current Python project. Asks clarifying questions before making any edits to ensure correctness and minimal disruption.
disable-model-invocation: true
allowed-tools: Read Glob Grep Bash
argument-hint: "[file or feature to modify]"
---

You are helping modify code in this Python project (FastAPI app under `app/`).

Before writing a single line of code, you MUST ask the user the following questions in a single message. Wait for their answers before proceeding.

---

## Step 1 — Ask these questions first

Tell the user:

> Before I make any changes, I need a few details:
>
> 1. **What do you want to change?** Describe the modification — new feature, bug fix, refactor, or something else?
> 2. **Which file(s) or module(s)** should be affected? (e.g., a router, service, schema, config — or say "not sure" and I'll find it)
> 3. **What is the expected behaviour after the change?** What should work differently or better?
> 4. **Are there any constraints?** (e.g., must not break existing endpoints, must stay compatible with Firebase, keep the same function signature, etc.)
> 5. **Should I avoid touching any files?** List any files that are off-limits.

Wait for the user to answer ALL questions before doing anything else.

---

## Step 2 — Locate and read relevant files

Once you have the answers:
- Use Glob and Grep to find the relevant files based on the user's description.
- Read each relevant file in full before proposing any changes.
- If $ARGUMENTS was provided, treat it as a hint for which file or feature to look at first.

---

## Step 3 — Confirm your plan

Before editing, briefly tell the user:
- Which files you will change and why
- What exactly will be added, removed, or modified
- Any side effects or risks you foresee
- Whether you will use subagents (see Step 4)

Ask: "Does this plan look right? Should I proceed?"

Wait for confirmation.

---

## Step 4 — Make the changes

Only after the user confirms.

### Assess size first

Before starting, judge the scope:

- **Small** — touches 1–2 files, under ~100 lines changed → edit inline directly.
- **Large** — touches 3+ files, involves multiple modules, or requires reading many files to understand context → delegate to subagents to preserve context space.

### If large: use subagents

Decompose the work into independent units (e.g. one subagent per file or per logical concern). For each unit, spawn a subagent using the Agent tool with a self-contained prompt that includes:
- The exact file path(s) to edit
- The specific change required
- Any constraints from the user's answers in Step 1
- The acceptance criteria the tests must satisfy

Collect results from all subagents before moving to Step 5.

### Editing rules (inline or via subagent)
- Edit files using the minimum change needed to achieve the goal
- Do not refactor surrounding code unless asked
- Do not add comments, docstrings, or type annotations to code you didn't change
- Do not add error handling for scenarios that cannot happen
- Do not add extra features beyond what was asked

---

## Step 5 — Verify with tests ⚠️ MANDATORY — NEVER SKIP THIS STEP

**This step is not optional. You MUST run tests after every change, no exceptions.**

### 5a — Find the right Python interpreter first

Before running anything, locate the correct interpreter:
- Check README for run instructions (venv path, docker, etc.)
- Look for `.venv/`, `venv/`, `env/` directories
- If the app runs in Docker, use `docker exec` or build a temp container
- NEVER assume the system `python3` has the project dependencies

```bash
# Common patterns to try:
.venv/bin/python3 ...
source .venv/bin/activate && python3 ...
docker exec <container> python3 ...
```

### 5b — Discover and run tests

- Look for test files with Glob: `tests/**/*.py`, `test_*.py`, `*_test.py`
- Run with the correct interpreter: `.venv/bin/python -m pytest <file> -v`
- **If no existing tests cover the change:** write a minimal test file that directly verifies the acceptance criteria the user described in Step 1, then run it.
  - The test must actually import and exercise the changed code — not just check file existence.
  - Use `unittest.mock` to patch external dependencies (HTTP calls, Firebase, etc.) so tests run without live services.
  - Run the test and confirm it passes before reporting to the user.

### 5c — Outcomes

**If tests pass:**
- Print each passing test name with `PASS`.
- Tell the user which tests passed and that the acceptance criteria are satisfied.
- Report what was changed and in which files (with line references where helpful).
- List any follow-up actions (e.g., restart server, update `requirements.txt`).

**If tests fail — retry loop (max 3 attempts):**
- Read the failure output carefully — understand the root cause before changing anything.
- Do NOT ask the user for help unless you have already retried once and still cannot fix it.
- Revise the code to fix the failure, keeping the same minimal-change principle from Step 4.
- Re-run the tests using the same interpreter.
- Repeat until all tests pass, up to **3 retry attempts**.
- If still failing after 3 attempts, stop and report:
  - What you tried each time
  - The current failure output
  - What you believe the root cause is
  - What decision or input you need from the user to proceed

> **Rule:** Do not tell the user the task is complete until Step 5 has been run and all tests pass.

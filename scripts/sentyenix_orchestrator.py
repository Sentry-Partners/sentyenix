#!/usr/bin/env python3
"""
Sentyenix Orchestrator — MAT Protocol v2.1

Builder/Quorum loop with convergence detection and scope guarding:

1. Codex (Builder) implements
2. Claude + Kimi (Quorum) review:
   a. Technical: Are bugs real? Getting fixed?
   b. Scope: Is work on-track or drifting?
3. Loop continues while progress is being made
4. Stop when: consensus, convergence, stall, or hazy call

Stop conditions:
- CONSENSUS: All quorum members APPROVE
- CONVERGENCE: All prior round issues addressed, no new critical issues
- STALL: Same issues reappear without progress (generational drift)
- HAZY: Quorum members disagree on scope/legitimacy → human needed
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ── Configuration ───────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "Sentry-Partners/sentyenix"
SENTYENIX_ROOT = Path.home() / ".kimi_openclaw" / "workspace" / "sentyenix"

MODEL_FAMILIES = {
    "claude": {
        "cli": "claude",
        "args": ["-p", "--permission-mode", "bypassPermissions"],
        "path": None,
        "role": "quorum",
        "auth_check": "claude -p 'hi' 2>&1 | head -1",
        "auth_fail_strings": ["Not logged in", "login", "Please run"],
    },
    "codex": {
        "cli": "codex",
        "args": ["exec", "--full-auto"],
        "path": None,
        "role": "builder",
        "auth_check": "codex -a never exec --skip-git-repo-check -s read-only 'hi' 2>&1 | head -1",
        "auth_fail_strings": ["auth", "login", "API key", "not authenticated"],
    },
    "kimi": {
        "cli": "kimi",
        "args": ["-p"],
        "path": "/Users/carlos/.kimi-code/bin",
        "role": "quorum",
        "auth_check": "export PATH='/Users/carlos/.kimi-code/bin:$PATH' && kimi -p 'hi' 2>&1 | head -1",
        "auth_fail_strings": ["not authenticated", "login", "unauthorized", "auth"],
    },
}

# ── GitHub API ──────────────────────────────────────────────────────────────

class GitHubAPI:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base = f"https://api.github.com/repos/{repo}"

    def get_issues(self, labels: str = "spawn", state: str = "open") -> List[Dict]:
        url = f"{self.base}/issues"
        params = {"labels": labels, "state": state, "per_page": 10}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_issue(self, number: int) -> Dict:
        url = f"{self.base}/issues/{number}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def create_comment(self, number: int, body: str) -> Dict:
        url = f"{self.base}/issues/{number}/comments"
        resp = requests.post(url, headers=self.headers, json={"body": body})
        resp.raise_for_status()
        return resp.json()

    def close_issue(self, number: int) -> Dict:
        url = f"{self.base}/issues/{number}"
        resp = requests.patch(url, headers=self.headers, json={"state": "closed"})
        resp.raise_for_status()
        return resp.json()

    def add_label(self, number: int, label: str) -> Dict:
        url = f"{self.base}/issues/{number}/labels"
        resp = requests.post(url, headers=self.headers, json={"labels": [label]})
        resp.raise_for_status()
        return resp.json()

# ── Registry ────────────────────────────────────────────────────────────────

class AgentRegistry:
    def __init__(self, root: Path):
        self.registry_file = root / "registry" / "agents.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.registry_file.exists():
            self.agents = json.loads(self.registry_file.read_text())
        else:
            self.agents = {"agents": [], "version": "2.1.0", "last_updated": None}

    def _save(self):
        self.agents["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.registry_file.write_text(json.dumps(self.agents, indent=2))

    def register(self, agent_id: str, name: str, model: str, camp: str, role: str) -> Dict:
        existing = self.get(agent_id)
        if existing:
            existing.update({
                "name": name,
                "model": model,
                "camp": camp,
                "role": role,
                "status": "active",
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            })
            self._save()
            return existing

        agent = {
            "id": agent_id,
            "name": name,
            "model": model,
            "camp": camp,
            "role": role,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trust_score": 0.5,
        }
        self.agents["agents"].append(agent)
        self._save()
        return agent

    def get(self, agent_id: str) -> Optional[Dict]:
        for agent in self.agents.get("agents", []):
            if agent.get("id") == agent_id:
                return agent
        return None

# ── Geno Project Memory ─────────────────────────────────────────────────────

class GenoProjectMemory:
    """Append-only project memory adapter for Sentyenix orchestration events."""

    def __init__(self, root: Path):
        self.memory_dir = root / ".geno"
        self.memory_file = self.memory_dir / "project-memory.jsonl"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, issue: Dict, payload: Optional[Dict] = None) -> Dict:
        record = {
            "schema_version": "geno.project_memory.v1",
            "event_type": event_type,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": f"github-issue-{issue['number']}",
                "source": "github_issue",
                "number": issue["number"],
                "title": issue.get("title", ""),
                "url": issue.get("html_url", ""),
            },
            "payload": payload or {},
        }
        with self.memory_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def read_project(self, issue_number: int) -> List[Dict]:
        if not self.memory_file.exists():
            return []
        project_id = f"github-issue-{issue_number}"
        records = []
        for line in self.memory_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("project", {}).get("id") == project_id:
                records.append(record)
        return records

# ── CLI Runner ──────────────────────────────────────────────────────────────

class CLIRunner:
    @staticmethod
    def build_env(cli_info: Dict) -> Dict:
        env = {**os.environ, "HOME": os.environ.get("HOME", str(Path.home()))}
        if cli_info.get("path"):
            env["PATH"] = f"{cli_info['path']}:{env.get('PATH', '')}"
        return env

    @staticmethod
    def run(cmd: List[str], cwd: Path, env: Dict, timeout: int = 300) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd), env=env)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"[TIMEOUT] {timeout}s"
        except FileNotFoundError as e:
            return -1, "", f"[NOT FOUND] {e}"

# ── Convergence Tracker ─────────────────────────────────────────────────────

class ConvergenceTracker:
    """Tracks issues across rounds to detect progress, stalls, or drift."""

    def __init__(self):
        self.rounds = []  # List of RoundState

    def add_round(self, round_num: int, reviews: List[Dict], diff: str):
        """Record a round's state."""
        issues = self._extract_issues(reviews)
        scope_votes = self._extract_scope_votes(reviews)

        state = {
            "round": round_num,
            "reviews": reviews,
            "issues": issues,  # List of found issues
            "scope_votes": scope_votes,  # {model: "on_track" | "legitimate_drift" | "scope_creep"}
            "diff_size": len(diff),
        }
        self.rounds.append(state)

    def _extract_issues(self, reviews: List[Dict]) -> List[str]:
        """Extract issue descriptions from reviews."""
        all_issues = []
        for r in reviews:
            text = r.get("raw_output", "")
            # Look for numbered issue lists
            issues = re.findall(r'(?i)(?:bug|issue|problem|concern|risk)[^\n]*\n([^\n]+)', text)
            all_issues.extend(issues[:5])  # Max 5 per reviewer
        return all_issues

    def _extract_scope_votes(self, reviews: List[Dict]) -> Dict[str, str]:
        """Extract scope assessment from reviews."""
        votes = {}
        for r in reviews:
            text = r.get("raw_output", "").lower()
            model = r.get("model", "unknown")
            if "scope creep" in text or "out of scope" in text or "drifting" in text:
                votes[model] = "scope_creep"
            elif "legitimate" in text or "should have anticipated" in text or "necessary extension" in text:
                votes[model] = "legitimate_drift"
            else:
                votes[model] = "on_track"
        return votes

    def assess(self) -> Tuple[str, str]:
        """
        Returns (status, reason) where status is:
        - CONSENSUS: All approve
        - CONVERGENCE: Issues getting fixed, no new critical issues
        - STALL: Same issues persisting without progress
        - HAZY: Quorum disagrees on scope
        """
        if not self.rounds:
            return "PENDING", "No rounds yet"

        latest = self.rounds[-1]
        reviews = latest.get("reviews", [])

        # Check for unanimous approval (guard against empty reviews)
        if not reviews:
            return "PENDING", "No reviews in this round"
        all_approve = all(r.get("verdict") == "APPROVE" for r in reviews)
        if all_approve:
            return "CONSENSUS", "All quorum members approve"

        # Check for scope disagreement (HAZY)
        scope_votes = latest.get("scope_votes", {})
        vote_values = list(scope_votes.values())
        if vote_values and len(set(vote_values)) > 1 and "scope_creep" in vote_values:
            # Mixed votes including scope creep concern
            return "HAZY", f"Quorum disagrees on scope: {scope_votes}"

        # Need at least 2 rounds to assess convergence
        if len(self.rounds) < 2:
            return "PENDING", "Need more rounds to assess convergence"

        prev = self.rounds[-2]
        prev_issues = set(self._normalize_issue(i) for i in prev["issues"])
        curr_issues = set(self._normalize_issue(i) for i in latest["issues"])

        # STALL: Same issues keep appearing
        persistent = curr_issues & prev_issues
        if len(persistent) == len(curr_issues) and len(curr_issues) > 0:
            return "STALL", f"Same issues persist: {persistent}"

        # CONVERGENCE: Prior issues addressed, maybe minor new ones
        fixed = prev_issues - curr_issues
        new = curr_issues - prev_issues
        critical_new = [issue for issue in new if self._is_critical_issue(issue)]
        if len(fixed) > 0 and len(new) <= len(fixed) and not critical_new:
            return "CONVERGENCE", f"Fixed {len(fixed)} issues, {len(new)} new minor issues"

        return "PENDING", f"Progressing: fixed {len(prev_issues - curr_issues)}, new {len(new)}"

    def _normalize_issue(self, issue: str) -> str:
        """Normalize issue text for comparison."""
        # Remove specific line numbers, file paths, etc.
        text = re.sub(r'\d+', 'N', issue.lower())
        text = re.sub(r'[/\.]\w+', 'FILE', text)
        return text[:80]

    def _is_critical_issue(self, issue: str) -> bool:
        """Detect issues that should block convergence even if other items improved."""
        critical_terms = (
            "critical",
            "security",
            "vulnerability",
            "data loss",
            "corruption",
            "regression",
            "crash",
            "blocking",
            "must fix",
            "unsafe",
        )
        return any(term in issue for term in critical_terms)

class CampProgressReporter:
    """Writes live progress updates so humans can see the camp isn't stuck."""

    def __init__(self, repo_root: Path, issue_number: int):
        self.repo_root = repo_root
        self.issue_number = issue_number
        self.progress_file = repo_root / f".camp-progress-{issue_number}.json"
        self.started = datetime.now(timezone.utc)

    def update(self, status: str, step: str, detail: str = ""):
        """Write current progress to JSON file."""
        elapsed = (datetime.now(timezone.utc) - self.started).total_seconds()
        data = {
            "issue_number": self.issue_number,
            "status": status,          # running | building | reviewing | assessing | done | error
            "step": step,              # e.g. "Builder Round 2: codex"
            "detail": detail,          # e.g. "Diff: 19839 chars"
            "elapsed_seconds": int(elapsed),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.progress_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass  # Don't let progress reporting break the camp

    def done(self, result: str, rounds: int):
        self.update("done", "Camp complete", f"{result} in {rounds} rounds")
        # Clean up progress file
        try:
            self.progress_file.unlink()
        except Exception:
            pass

class MATOrchestrator:
    def __init__(self, github: GitHubAPI, registry: AgentRegistry, repo_root: Path, geno_memory: GenoProjectMemory):
        self.github = github
        self.registry = registry
        self.repo_root = repo_root
        self.geno_memory = geno_memory
        self.runner = CLIRunner()
        self.tracker = ConvergenceTracker()
        self.progress = None  # type: CampProgressReporter | None

    def check_model(self, model: str) -> bool:
        cli_info = MODEL_FAMILIES.get(model)
        if not cli_info:
            return False
        env = self.runner.build_env(cli_info)
        rc, _, _ = self.runner.run(["which", cli_info["cli"]], self.repo_root, env, timeout=5)
        if rc != 0:
            return False
        if "auth_check" in cli_info:
            rc, out, err = self.runner.run(cli_info["auth_check"], self.repo_root, env, timeout=10)
            output = (out + err).lower()
            for fail in cli_info.get("auth_fail_strings", []):
                if fail.lower() in output:
                    return False
        return True

    def get_git_diff(self) -> str:
        env = self.runner.build_env({})
        rc, stdout, _ = self.runner.run(["git", "diff", "HEAD"], self.repo_root, env, timeout=30)
        return stdout if rc == 0 else ""

    def reset_to_head(self):
        """Reset any uncommitted changes before a new build round."""
        env = self.runner.build_env({})
        self.runner.run(["git", "checkout", "--", "."], self.repo_root, env, timeout=10)
        self.runner.run(["git", "clean", "-fd"], self.repo_root, env, timeout=10)

    def run_builder(self, issue: Dict, round_num: int, feedback: str, scope_extended: bool = False) -> Tuple[str, str]:
        model = "codex"
        cli_info = MODEL_FAMILIES[model]
        env = self.runner.build_env(cli_info)

        agent_id = f"builder-{model}-{issue['number']}-r{round_num}"
        self.registry.register(agent_id, f"Builder ({model}) R{round_num}", model, f"Issue-{issue['number']}", "builder")

        title = issue.get("title", "")
        body = issue.get("body", "")

        if round_num == 0:
            prompt = f"""You are the Builder. Implement this issue in the repository at {self.repo_root}.

Issue: {title}
Description: {body}

Make focused, minimal changes that solve the issue. Stop when done. Do not commit or push.
"""
        else:
            prompt = f"""You are the Builder fixing issues from the Quorum review.

Issue: {title}

Quorum feedback from previous round:
{feedback}

Current diff:
```diff
{self.get_git_diff()}
```

Address ALL feedback. Make focused changes. Stop when done. Do not commit or push.
"""

        cmd = [cli_info["cli"]] + cli_info["args"] + [prompt]
        print(f"\n  🔨 Builder R{round_num}: {model} building...")

        rc, stdout, stderr = self.runner.run(cmd, self.repo_root, env, timeout=300)
        output = stdout
        if rc != 0 and stderr:
            output += f"\n[BUILDER ERR]: {stderr[:500]}"

        diff = self.get_git_diff()
        print(f"    Diff: {len(diff)} chars")
        return output, diff

    def run_reviewer(self, issue: Dict, model: str, round_num: int, diff: str, prior_reviews: str = "") -> Dict:
        cli_info = MODEL_FAMILIES[model]
        env = self.runner.build_env(cli_info)

        agent_id = f"quorum-{model}-{issue['number']}-r{round_num}"
        self.registry.register(agent_id, f"Quorum ({model}) R{round_num}", model, f"Issue-{issue['number']}", "quorum")

        prompt = f"""You are a Quorum Reviewer. Review this code diff for the issue.

Issue: {issue.get('title', '')}

```diff
{diff[:10000]}
```

Respond in this EXACT format:

TECHNICAL_VERDICT: APPROVE or REQUEST_CHANGES
SCOPE_ASSESSMENT: ON_TRACK or LEGITIMATE_DRIFT or SCOPE_CREEP
ALIGNMENT: 0.0-1.0

TECHNICAL_REVIEW:
1. Assessment of the changes
2. Bugs, security issues, or problems found (be specific)
3. Specific changes needed (if any)

SCOPE_REVIEW:
1. Is this work still on track for the original issue?
2. If there's new work, is it a legitimate extension the original plan should have anticipated?
3. Or is this scope creep?
"""

        cmd = [cli_info["cli"]] + cli_info["args"] + [prompt]
        print(f"\n  🧐 Quorum ({model}): Reviewing...")

        rc, stdout, stderr = self.runner.run(cmd, self.repo_root, env, timeout=300)
        output = stdout
        if rc != 0 and stderr:
            output += f"\n[REVIEWER ERR]: {stderr[:500]}"

        review = self._parse_review(output)
        review["raw_output"] = output
        review["model"] = model

        emoji = "✅" if review["verdict"] == "APPROVE" else "❌"
        scope_emoji = {"ON_TRACK": "🎯", "LEGITIMATE_DRIFT": "📐", "SCOPE_CREEP": "🚫"}.get(review["scope"], "❓")
        print(f"    {emoji} {model}: {review['verdict']} | {scope_emoji} {review['scope']} | align: {review['alignment']:.2f}")

        return review

    def _parse_review(self, text: str) -> Dict:
        text_lower = text.lower()

        # Technical verdict
        verdict = "REQUEST_CHANGES"
        if "technical_verdict: approve" in text_lower:
            verdict = "APPROVE"

        # Scope assessment
        scope = "ON_TRACK"
        if "scope_creep" in text_lower or "scope assessment: scope_creep" in text_lower:
            scope = "SCOPE_CREEP"
        elif "legitimate_drift" in text_lower or "scope assessment: legitimate_drift" in text_lower:
            scope = "LEGITIMATE_DRIFT"

        # Alignment
        alignment = 0.5
        match = re.search(r'alignment[:\s]+(\d+\.?\d*)', text_lower)
        if match:
            alignment = max(0.0, min(1.0, float(match.group(1))))

        return {"verdict": verdict, "scope": scope, "alignment": alignment}

    def process_issue(self, issue: Dict) -> None:
        number = issue["number"]
        print(f"\n{'='*60}")
        print(f"🏗️  MAT Camp — Issue #{number}: {issue.get('title', '')}")
        print(f"{'='*60}")

        # Initialize progress reporter
        self.progress = CampProgressReporter(self.repo_root, number)
        self.progress.update("running", "Camp initializing", "Checking model availability")
        self.geno_memory.record("camp_started", issue, {"status": "running"})

        # Post "camp started" comment so user can watch live
        self.github.create_comment(
            number,
            f"🏕️ **MAT Camp started** — Builder/Quorum loop running\n"
            f"- Models checking...\n"
            f"- Live progress: watch this issue for round-by-round updates\n"
            f"- Started: {datetime.now(timezone.utc).isoformat()}"
        )

        # Check models
        available = {m: self.check_model(m) for m in MODEL_FAMILIES}
        print(f"\nModels: " + " ".join(f"{'✅' if v else '❌'} {k}" for k, v in available.items()))

        if not available.get("codex"):
            print("❌ No builder available")
            self.progress.update("error", "No builder available", "Codex CLI not found or not authenticated")
            self.geno_memory.record("camp_aborted", issue, {"reason": "Codex builder not available"})
            self.github.create_comment(number, "❌ **Camp aborted:** Codex builder not available.")
            return

        quorum = [m for m in ["claude", "kimi"] if available.get(m)]
        if len(quorum) < 1:
            print("⚠️  No quorum — running builder once")

        self.progress.update("running", f"Camp active | Quorum: {', '.join(quorum)}", "Starting build rounds")

        # Run build/quorum loop
        self.tracker = ConvergenceTracker()
        round_num = 0
        feedback = ""
        scope_extended = False
        round_reports = []

        while True:
            print(f"\n{'─'*50}")
            print(f"📐 ROUND {round_num + 1}")
            print(f"{'─'*50}")
            self.progress.update("building", f"Round {round_num + 1}", "Builder (codex) working...")

            # Reset repo before building (except round 0 where we keep prior work)
            if round_num > 0:
                self.reset_to_head()

            # Builder
            builder_output, diff = self.run_builder(issue, round_num, feedback, scope_extended)

            if not diff.strip():
                print("⚠️  No diff produced")
                self.progress.update("error", f"Round {round_num + 1}", "Builder produced no diff")
                break

            self.progress.update("reviewing", f"Round {round_num + 1}", f"Diff: {len(diff)} chars. Quorum reviewing...")

            # Quorum
            reviews = []
            if quorum:
                for model in quorum:
                    self.progress.update("reviewing", f"Round {round_num + 1}", f"Quorum ({model}) reviewing...")
                    review = self.run_reviewer(issue, model, round_num, diff, feedback)
                    reviews.append(review)

                # Track this round
                self.tracker.add_round(round_num, reviews, diff)
                status, reason = self.tracker.assess()

                round_reports.append({
                    "round": round_num + 1,
                    "diff": diff,
                    "reviews": reviews,
                    "status": status,
                    "reason": reason,
                })
                self.geno_memory.record("round_reviewed", issue, {
                    "round": round_num + 1,
                    "status": status,
                    "reason": reason,
                    "diff_chars": len(diff),
                    "reviews": [
                        {
                            "model": r.get("model"),
                            "verdict": r.get("verdict"),
                            "scope": r.get("scope"),
                            "alignment": r.get("alignment"),
                        }
                        for r in reviews
                    ],
                })

                self.progress.update("assessing", f"Round {round_num + 1}", f"Status: {status} — {reason}")
                print(f"\n  📊 Camp Status: {status} — {reason}")

                # Post round update to GitHub issue (live progress!)
                round_summary = self._format_round_summary(round_num + 1, reviews, status, diff)
                self.github.create_comment(number, round_summary)

                # Decision tree
                if status == "CONSENSUS":
                    print(f"\n✅ CONSENSUS reached")
                    break
                elif status == "CONVERGENCE":
                    print(f"\n✅ CONVERGENCE — issues being fixed, minor new ones acceptable")
                    break
                elif status == "STALL":
                    print(f"\n🛑 STALL — generational drift detected")
                    break
                elif status == "HAZY":
                    print(f"\n🌫️  HAZY — quorum disagrees, needs human")
                    break
                else:
                    # Continue to next round
                    feedback_parts = []
                    for r in reviews:
                        if r["verdict"] != "APPROVE":
                            feedback_parts.append(f"\n--- {r['model'].capitalize()} ---\n{r['raw_output'][:2000]}")
                    feedback = "\n".join(feedback_parts)

                    scope_votes = [r["scope"] for r in reviews]
                    if "LEGITIMATE_DRIFT" in scope_votes and "SCOPE_CREEP" not in scope_votes:
                        scope_extended = True
                        print("    📐 Scope extended (legitimate drift approved by quorum)")
            else:
                round_reports.append({"round": 1, "diff": diff, "reviews": [], "status": "NO_QUORUM", "reason": "No quorum available"})
                self.geno_memory.record("round_reviewed", issue, {
                    "round": 1,
                    "status": "NO_QUORUM",
                    "reason": "No quorum available",
                    "diff_chars": len(diff),
                    "reviews": [],
                })
                break

            round_num += 1
            if round_num >= 10:  # Safety cap
                print("\n🛑 SAFETY CAP reached (10 rounds)")
                self.progress.update("error", f"Round {round_num}", "Safety cap reached (10 rounds)")
                break

        # Post final report
        self._post_report(issue, round_reports)

    def _format_round_summary(self, round_num: int, reviews: List[Dict], status: str, diff: str) -> str:
        """Format a live round update for posting to GitHub."""
        lines = [f"### 📐 Round {round_num} Complete", ""]
        lines.append(f"**Status:** {status}")
        lines.append(f"**Diff:** {len(diff)} chars")
        lines.append("")
        for r in reviews:
            emoji = "✅" if r["verdict"] == "APPROVE" else "❌"
            scope = r.get("scope", "?")
            lines.append(f"- {emoji} **{r['model'].capitalize()}**: {r['verdict']} | scope: {scope} | align: {r['alignment']:.2f}")
        lines.append("")
        if status == "PENDING":
            lines.append("⏳ **Next:** Sending feedback to Builder for fixes...")
        elif status == "CONSENSUS":
            lines.append("✅ **Consensus reached!** Preparing final report...")
        elif status == "CONVERGENCE":
            lines.append("✅ **Convergence reached!** Issues fixed, minor new ones acceptable.")
        elif status == "STALL":
            lines.append("🛑 **Stalled.** Same issues persisting. Needs human.")
        elif status == "HAZY":
            lines.append("🌫️ **Hazy call.** Quorum disagrees on scope. Needs human.")
        return "\n".join(lines)

    def _post_report(self, issue: Dict, round_reports: List[Dict]):
        number = issue["number"]

        final = round_reports[-1] if round_reports else {"status": "UNKNOWN", "reason": "No rounds"}
        status = final["status"]

        report = f"""## 🏕️ MAT Camp Report

**Issue:** {issue.get('title', 'Unknown')}
**Final Status:** {status}
**Rounds:** {len(round_reports)}
**Time:** {datetime.now(timezone.utc).isoformat()}

### Build Rounds
"""
        for r in round_reports:
            report += f"\n#### Round {r['round']} — {r['status']}\n"
            report += f"- Diff: {len(r['diff'])} chars\n"
            for review in r.get("reviews", []):
                emoji = "✅" if review["verdict"] == "APPROVE" else "❌"
                scope = review.get("scope", "?")
                report += f"- {emoji} **{review['model'].capitalize()}**: {review['verdict']} | scope: {scope} | align: {review['alignment']:.2f}\n"

        report += f"\n### Decision\n"
        if status in ("CONSENSUS", "CONVERGENCE"):
            report += "✅ **Camp approves.** Ready for human review/merge.\n"
            self.github.close_issue(number)
        elif status == "STALL":
            report += "🛑 **Stalled.** Builder unable to resolve persistent issues. Needs human.\n"
        elif status == "HAZY":
            report += "🌫️ **Hazy call.** Quorum disagrees on scope/legitimacy. Needs human.\n"
        else:
            report += "⚠️ **Incomplete.** Camp ended without clear resolution. Needs human.\n"

        self.github.create_comment(number, report)
        self.github.add_label(number, "camp-complete")
        if self.progress:
            self.progress.done(status, len(round_reports))
        self.geno_memory.record("camp_completed", issue, {
            "status": status,
            "rounds": len(round_reports),
            "reason": final.get("reason", ""),
        })
        print(f"\n📋 Report posted to Issue #{number}")

    def poll(self, interval: int = 60):
        print(f"MAT Orchestrator v2.1 starting...")
        print(f"Repo: {GITHUB_REPO}")
        processed = set()

        while True:
            try:
                issues = self.github.get_issues(labels="spawn,auto", state="open")
                print(f"[{datetime.now(timezone.utc).isoformat()}] {len(issues)} open spawn issues")

                for issue in issues:
                    number = issue["number"]
                    if number in processed:
                        continue
                    labels = [l["name"] for l in issue.get("labels", [])]
                    if "camp-complete" in labels:
                        processed.add(number)
                        continue

                    self.process_issue(issue)
                    processed.add(number)

                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(interval)

# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MAT Orchestrator v2.1")
    parser.add_argument("--mode", choices=["poll", "single"], default="poll")
    parser.add_argument("--issue", type=int)
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN required")
        sys.exit(1)

    github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO)
    registry = AgentRegistry(SENTYENIX_ROOT)
    geno_memory = GenoProjectMemory(SENTYENIX_ROOT)
    orchestrator = MATOrchestrator(github, registry, SENTYENIX_ROOT, geno_memory)

    if args.mode == "poll":
        orchestrator.poll(args.interval)
    elif args.mode == "single":
        if args.issue is None:
            print("ERROR: --issue required")
            sys.exit(1)
        issue = github.get_issue(args.issue)
        orchestrator.process_issue(issue)

if __name__ == "__main__":
    main()

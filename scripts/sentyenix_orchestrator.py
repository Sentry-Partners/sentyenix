#!/usr/bin/env python3
"""
Sentyenix Orchestrator — Builder/Quorum MAT Protocol

Flow:
1. Codex (Builder) implements the issue
2. Claude + Kimi (Quorum) review the diff
3. If consensus not reached, Builder fixes based on feedback
4. Repeat until consensus or max rounds

Usage:
    python sentyenix_orchestrator.py --mode single --issue 42
    python sentyenix_orchestrator.py --mode poll --interval 60
"""

import argparse
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
MAX_BUILD_ROUNDS = 3

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

# ── Agent Registry ──────────────────────────────────────────────────────────

class AgentRegistry:
    def __init__(self, root: Path):
        self.registry_file = root / "registry" / "agents.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.registry_file.exists():
            self.agents = json.loads(self.registry_file.read_text())
        else:
            self.agents = {"agents": [], "version": "2.0.0", "last_updated": None}

    def _save(self):
        self.agents["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.registry_file.write_text(json.dumps(self.agents, indent=2))

    def register(self, agent_id: str, name: str, model: str, camp: str, role: str) -> Dict:
        agent = {
            "id": agent_id,
            "name": name,
            "model": model,
            "camp": camp,
            "role": role,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trust_score": 0.5,
            "build_rounds": 0,
            "reviews_completed": 0,
        }
        self.agents["agents"].append(agent)
        self._save()
        return agent

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        for a in self.agents["agents"]:
            if a["id"] == agent_id:
                return a
        return None

    def update_field(self, agent_id: str, field: str, value):
        agent = self.get_agent(agent_id)
        if agent:
            agent[field] = value
            self._save()

# ── CLI Runner ──────────────────────────────────────────────────────────────

class CLIRunner:
    """Runs model CLI commands with proper env setup."""

    @staticmethod
    def build_env(cli_info: Dict) -> Dict:
        env = {**os.environ, "HOME": os.environ.get("HOME", str(Path.home()))}
        if cli_info.get("path"):
            env["PATH"] = f"{cli_info['path']}:{env.get('PATH', '')}"
        return env

    @staticmethod
    def run(cmd: List[str], cwd: Path, env: Dict, timeout: int = 300) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
                env=env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"[TIMEOUT] Command timed out after {timeout}s"
        except FileNotFoundError as e:
            return -1, "", f"[NOT FOUND] {e}"

    @staticmethod
    def run_shell(cmd: str, cwd: Path, env: Dict, timeout: int = 300) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
                env=env,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"[TIMEOUT] Command timed out after {timeout}s"
        except FileNotFoundError as e:
            return -1, "", f"[NOT FOUND] {e}"

# ── Builder / Quorum Orchestrator ───────────────────────────────────────────

class BuilderQuorumOrchestrator:
    """
    Builder/Quorum loop:
    1. Codex builds implementation
    2. Claude + Kimi review the diff
    3. If not consensus, Codex fixes based on feedback
    4. Repeat until consensus or max rounds
    """

    def __init__(self, github: GitHubAPI, registry: AgentRegistry, repo_root: Path):
        self.github = github
        self.registry = registry
        self.repo_root = repo_root
        self.runner = CLIRunner()

    def check_model_available(self, model: str) -> bool:
        cli_info = MODEL_FAMILIES.get(model)
        if not cli_info:
            return False

        env = self.runner.build_env(cli_info)

        # Check binary exists
        rc, _, _ = self.runner.run(["which", cli_info["cli"]], self.repo_root, env, timeout=5)
        if rc != 0:
            return False

        # Check auth
        if "auth_check" in cli_info:
            rc, stdout, stderr = self.runner.run_shell(
                cli_info["auth_check"], self.repo_root, env, timeout=10
            )
            output = (stdout + stderr).lower()
            for fail_str in cli_info.get("auth_fail_strings", []):
                if fail_str.lower() in output:
                    return False

        return True

    def get_git_diff(self) -> str:
        """Get current diff from repo root."""
        env = self.runner.build_env({})
        rc, stdout, stderr = self.runner.run_shell(
            "git diff HEAD", self.repo_root, env, timeout=30
        )
        if rc != 0:
            return f"[ERROR getting diff: {stderr[:200]}]"
        return stdout

    def run_builder(self, issue: Dict, round_num: int, prior_feedback: str = "") -> Tuple[str, str]:
        """Run Codex as builder. Returns (output, diff)."""
        model = "codex"
        cli_info = MODEL_FAMILIES[model]
        env = self.runner.build_env(cli_info)

        agent_id = f"builder-codex-{issue['number']}-r{round_num}"
        agent = self.registry.register(agent_id, f"Builder (Codex) R{round_num}", model, f"Issue-{issue['number']}", "builder")

        title = issue.get("title", "")
        body = issue.get("body", "")

        if round_num == 0:
            prompt = f"""You are the Builder for this issue.

Issue: {title}
Description: {body}

Your task: Implement the necessary code changes in the repository at {self.repo_root}.
Make focused, minimal changes that solve the issue.
When you are done making changes, stop. Do not commit or push.
"""
        else:
            prompt = f"""You are the Builder fixing issues identified by the Quorum.

Issue: {title}

Previous round feedback from Quorum:
{prior_feedback}

Current diff in the repo:
```diff
{self.get_git_diff()}
```

Your task: Address ALL the feedback above. Make additional changes as needed.
When done, stop. Do not commit or push.
"""

        cmd = [cli_info["cli"]] + cli_info["args"] + [prompt]
        print(f"\n  🔨 Builder Round {round_num}: Codex building...")

        rc, stdout, stderr = self.runner.run(cmd, self.repo_root, env, timeout=300)

        # Build output includes both stdout and any error info
        output = stdout
        if rc != 0 and stderr:
            output += f"\n[BUILDER STDERR]: {stderr[:500]}"

        # Capture the diff after building
        diff = self.get_git_diff()

        self.registry.update_field(agent_id, "build_rounds", round_num + 1)
        print(f"    Diff size: {len(diff)} chars")

        return output, diff

    def run_reviewer(self, issue: Dict, model: str, round_num: int, diff: str) -> Dict:
        """Run a quorum member (Claude or Kimi) as reviewer. Returns parsed review."""
        cli_info = MODEL_FAMILIES[model]
        env = self.runner.build_env(cli_info)

        agent_id = f"quorum-{model}-{issue['number']}-r{round_num}"
        agent = self.registry.register(agent_id, f"Quorum ({model.capitalize()}) R{round_num}", model, f"Issue-{issue['number']}", "quorum")

        title = issue.get("title", "")

        prompt = f"""You are a Quorum Reviewer reviewing code changes for this issue.

Issue: {title}

Here is the diff produced by the Builder:
```diff
{diff[:8000]}
```

Review this code carefully. Respond in this exact format:

VERDICT: APPROVE or REQUEST_CHANGES

REVIEW:
1. Your assessment of the changes
2. Any bugs, security issues, or problems
3. Specific changes needed (if any)

ALIGNMENT: Score 0.0-1.0 (how well does this align with clean code, safety, correctness)
"""

        cmd = [cli_info["cli"]] + cli_info["args"] + [prompt]
        print(f"\n  🧐 Quorum ({model}): Reviewing...")

        rc, stdout, stderr = self.runner.run(cmd, self.repo_root, env, timeout=300)

        output = stdout
        if rc != 0 and stderr:
            output += f"\n[REVIEWER STDERR]: {stderr[:500]}"

        self.registry.update_field(agent_id, "reviews_completed", round_num + 1)

        # Parse the review
        review = self._parse_review(output)
        review["raw_output"] = output
        review["model"] = model

        verdict_emoji = "✅" if review["verdict"] == "APPROVE" else "❌"
        print(f"    {verdict_emoji} Verdict: {review['verdict']} (alignment: {review['alignment']:.2f})")

        return review

    def _parse_review(self, text: str) -> Dict:
        """Parse structured review output."""
        text_lower = text.lower()

        # Check for explicit verdict
        verdict = "REQUEST_CHANGES"
        if "verdict: approve" in text_lower or "verdict:approve" in text_lower:
            verdict = "APPROVE"
        elif "approve" in text_lower and "request_changes" not in text_lower:
            verdict = "APPROVE"

        # Extract alignment score
        alignment = 0.5
        alignment_match = re.search(r'alignment[:\s]+(\d+\.?\d*)', text_lower)
        if alignment_match:
            alignment = float(alignment_match.group(1))
            alignment = max(0.0, min(1.0, alignment))

        # Extract review body (everything after "REVIEW:")
        review_body = text
        review_match = re.search(r'(?i)review[:\n](.*)', text, re.DOTALL)
        if review_match:
            review_body = review_match.group(1).strip()

        return {
            "verdict": verdict,
            "alignment": alignment,
            "review_body": review_body,
        }

    def check_consensus(self, reviews: List[Dict]) -> Tuple[bool, str]:
        """Check if quorum has reached consensus. Returns (consensus_reached, feedback)."""
        if not reviews:
            return False, "No reviews received."

        all_approve = all(r["verdict"] == "APPROVE" for r in reviews)
        avg_alignment = sum(r["alignment"] for r in reviews) / len(reviews)

        if all_approve and avg_alignment >= 0.7:
            return True, "Quorum unanimously approves."

        # Collect feedback for next round
        feedback_parts = []
        for r in reviews:
            if r["verdict"] != "APPROVE":
                feedback_parts.append(f"\n--- {r['model'].capitalize()} Reviewer ---\n{r['review_body'][:1500]}")

        feedback = "\n".join(feedback_parts) if feedback_parts else "Quorum requests changes."
        return False, feedback

    def process_issue(self, issue: Dict) -> None:
        """Run the full builder/quorum loop for an issue."""
        number = issue["number"]
        title = issue["title"]

        print(f"\n{'='*60}")
        print(f"🏗️  Builder/Quorum Loop — Issue #{number}: {title}")
        print(f"{'='*60}")

        # Check which models are available
        available = {m: self.check_model_available(m) for m in MODEL_FAMILIES}
        print(f"\nModel availability:")
        for model, avail in available.items():
            emoji = "✅" if avail else "❌"
            print(f"  {emoji} {model} ({MODEL_FAMILIES[model]['role']})")

        if not available.get("codex"):
            print("❌ ERROR: Codex (builder) not available. Cannot proceed.")
            return

        quorum_models = [m for m in ["claude", "kimi"] if available.get(m)]
        if len(quorum_models) < 1:
            print("⚠️ WARNING: No quorum reviewers available. Running builder only.")

        # Run build rounds
        diff = ""
        consensus_reached = False
        final_feedback = ""
        round_reports = []

        for round_num in range(MAX_BUILD_ROUNDS):
            print(f"\n{'─'*50}")
            print(f"📐 BUILD ROUND {round_num + 1}/{MAX_BUILD_ROUNDS}")
            print(f"{'─'*50}")

            # Builder phase
            builder_output, diff = self.run_builder(issue, round_num, final_feedback)

            if not diff.strip() or diff.startswith("[ERROR"):
                print("⚠️  No diff produced. Stopping.")
                break

            # Quorum phase
            reviews = []
            if quorum_models:
                for model in quorum_models:
                    review = self.run_reviewer(issue, model, round_num, diff)
                    reviews.append(review)

                consensus_reached, final_feedback = self.check_consensus(reviews)

                round_report = {
                    "round": round_num + 1,
                    "builder_output": builder_output,
                    "diff": diff,
                    "reviews": reviews,
                    "consensus": consensus_reached,
                }
                round_reports.append(round_report)

                if consensus_reached:
                    print(f"\n✅ CONSENSUS REACHED at round {round_num + 1}")
                    break
                else:
                    print(f"\n❌ No consensus. Feedback collected for next round.")
                    if round_num < MAX_BUILD_ROUNDS - 1:
                        print("    → Sending feedback to Builder for fixes...")
            else:
                # No quorum, just one-shot build
                consensus_reached = True
                final_feedback = "No quorum available. Builder output accepted."
                break

        # Final report
        self._post_final_report(issue, round_reports, consensus_reached, diff)

    def _post_final_report(self, issue: Dict, round_reports: List[Dict], consensus: bool, final_diff: str):
        """Post the final camp report to GitHub."""
        number = issue["number"]

        report = f"""## 🏕️ Builder/Quorum Camp Report

**Issue:** {issue.get('title', 'Unknown')}
**Consensus:** {'✅ Reached' if consensus else '❌ Not reached (max rounds)'}
**Rounds:** {len(round_reports)}
**Time:** {datetime.now(timezone.utc).isoformat()}

### Build Rounds
"""
        for r in round_reports:
            report += f"\n#### Round {r['round']}\n"
            report += f"- **Builder:** Codex\n"
            report += f"- **Diff size:** {len(r['diff'])} chars\n"
            report += f"- **Consensus:** {'✅ Yes' if r['consensus'] else '❌ No'}\n"

            for review in r["reviews"]:
                emoji = "✅" if review["verdict"] == "APPROVE" else "❌"
                report += f"\n**{emoji} {review['model'].capitalize()} Reviewer** (alignment: {review['alignment']:.2f})\n"
                report += f"```\n{review['review_body'][:800]}\n```\n"

        report += f"\n### Final Diff\n"
        report += f"```diff\n{final_diff[:2000]}\n```\n"
        if len(final_diff) > 2000:
            report += f"*(truncated — full diff in working tree)*\n"

        report += f"\n### Next Steps\n"
        if consensus:
            report += "- ✅ Quorum approves. Ready for human review and merge.\n"
        else:
            report += "- ❌ Quorum did not reach consensus within max rounds. Needs human intervention.\n"

        self.github.create_comment(number, report)
        self.github.add_label(number, "camp-complete")

        if consensus:
            print(f"\n✅ Issue #{number} marked camp-complete (consensus reached)")
        else:
            print(f"\n⚠️ Issue #{number} marked camp-complete (no consensus — needs human)")

# ── Backwards-compatible Orchestrator wrapper ───────────────────────────────

class Orchestrator:
    """Wrapper that routes to BuilderQuorumOrchestrator."""

    def __init__(self, github: GitHubAPI, registry: AgentRegistry, spawner, scorer, repo_root: Path):
        self.bq = BuilderQuorumOrchestrator(github, registry, repo_root)

    def process_issue(self, issue: Dict) -> None:
        self.bq.process_issue(issue)

    def poll(self, interval: int = 60):
        print(f"Sentyenix Orchestrator starting (Builder/Quorum mode)...")
        print(f"Repo: {GITHUB_REPO}")
        print(f"Polling interval: {interval}s")
        print(f"Press Ctrl+C to stop\n")

        processed = set()

        while True:
            try:
                issues = self.bq.github.get_issues(labels="spawn,auto", state="open")
                print(f"[{datetime.now(timezone.utc).isoformat()}] Found {len(issues)} open spawn issues")

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
                print(f"Error during poll: {e}")
                time.sleep(interval)

# Monkey-patch GitHubAPI for poll mode
def _get_issues(self, labels: str = "spawn", state: str = "open") -> List[Dict]:
    url = f"{self.base}/issues"
    params = {"labels": labels, "state": state, "per_page": 10}
    resp = requests.get(url, headers=self.headers, params=params)
    resp.raise_for_status()
    return resp.json()

GitHubAPI.get_issues = _get_issues

# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sentyenix Orchestrator")
    parser.add_argument("--mode", choices=["poll", "single", "registry"], default="poll")
    parser.add_argument("--issue", type=int, help="Issue number for single mode")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN environment variable required")
        sys.exit(1)

    github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO)
    registry = AgentRegistry(SENTYENIX_ROOT)
    spawner = None  # Not used in builder/quorum mode
    scorer = None   # Not used in builder/quorum mode
    orchestrator = Orchestrator(github, registry, spawner, scorer, SENTYENIX_ROOT)

    if args.mode == "poll":
        orchestrator.poll(args.interval)
    elif args.mode == "single":
        if args.issue is None:
            print("ERROR: --issue required for single mode")
            sys.exit(1)
        issue = github.get_issue(args.issue)
        orchestrator.process_issue(issue)
    elif args.mode == "registry":
        print(f"Agent Registry ({len(registry.all_agents())} agents):")
        for a in registry.all_agents():
            print(f"  {a['name']} ({a['model']}) - camp={a['camp']}, role={a['role']}, trust={a['trust_score']:.2f}")

if __name__ == "__main__":
    main()

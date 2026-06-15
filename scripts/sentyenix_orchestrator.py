#!/usr/bin/env python3
"""
Sentyenix Orchestrator

Local orchestrator that:
1. Polls GitHub for [SPAWN] issues
2. Spawns multi-lineage camps using Claude/Codex CLI
3. Coordinates camp deliberation
4. Reports results back to GitHub
5. Manages the agent registry

Usage:
    python sentyenix_orchestrator.py --mode poll --interval 60
    python sentyenix_orchestrator.py --mode single --issue 42
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

# ── Configuration ───────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "Sentry-Partners/sentyenix"
SENTYENIX_ROOT = Path.home() / ".kimi_openclaw" / "workspace" / "sentyenix"

# Model families available for multi-lineage camps
MODEL_FAMILIES = {
    "claude": {
        "cli": "claude",
        "args": ["-p", "--permission-mode", "bypassPermissions", "--bare"],
        "output_redirect": None,  # -p prints directly to stdout
    },
    "codex": {
        "cli": "codex",
        "args": ["-a", "never", "exec", "--skip-git-repo-check", "-s", "read-only"],
        "output_redirect": None,
    },
    # Grok and Kimi can be added when their CLIs are available
    # "grok": ...
    # "kimi": ...
    # "gemma": {"cli": "ollama", "args": ["run", "gemma4:31b"], "output_redirect": None}
}

# ── GitHub API ────────────────────────────────────────────────────────────────

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

    def get_issue_comments(self, number: int) -> List[Dict]:
        url = f"{self.base}/issues/{number}/comments"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def create_issue(self, title: str, body: str, labels: List[str]) -> Dict:
        url = f"{self.base}/issues"
        resp = requests.post(url, headers=self.headers, json={
            "title": title,
            "body": body,
            "labels": labels,
        })
        resp.raise_for_status()
        return resp.json()

    def get_file(self, path: str, ref: str = "main") -> str:
        url = f"{self.base}/contents/{path}"
        resp = requests.get(url, headers=self.headers, params={"ref": ref})
        resp.raise_for_status()
        data = resp.json()
        import base64
        return base64.b64decode(data["content"]).decode("utf-8")

# ── Agent Registry ───────────────────────────────────────────────────────────

class AgentRegistry:
    def __init__(self, root: Path):
        self.registry_file = root / "registry" / "agents.json"
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.registry_file.exists():
            self.agents = json.loads(self.registry_file.read_text())
        else:
            self.agents = {"agents": [], "version": "1.0.0", "last_updated": None}

    def _save(self):
        self.agents["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.registry_file.write_text(json.dumps(self.agents, indent=2))

    def register(self, agent_id: str, name: str, model: str, temperature: float,
                 camp: str, role: str, capabilities: List[str]) -> Dict:
        import hashlib
        signature = hashlib.sha256(f"{agent_id}:{model}:{temperature}:{camp}".encode()).hexdigest()[:16]
        agent = {
            "id": agent_id,
            "name": name,
            "model": model,
            "temperature": temperature,
            "camp": camp,
            "role": role,
            "capabilities": capabilities,
            "genetic_signature": signature,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trust_score": 0.5,  # Start at probation
            "alignment_history": [],
            "interaction_count": 0,
        }
        self.agents["agents"].append(agent)
        self._save()
        return agent

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        for a in self.agents["agents"]:
            if a["id"] == agent_id:
                return a
        return None

    def list_by_camp(self, camp: str) -> List[Dict]:
        return [a for a in self.agents["agents"] if a["camp"] == camp and a["status"] == "active"]

    def update_score(self, agent_id: str, alignment: float):
        agent = self.get_agent(agent_id)
        if agent:
            agent["alignment_history"].append(alignment)
            agent["interaction_count"] += 1
            # Simple trust score calculation
            recent = agent["alignment_history"][-10:]
            avg = sum(recent) / len(recent) if recent else 0.5
            agent["trust_score"] = min(0.9, 0.3 + avg * 0.6)
            self._save()

    def all_agents(self) -> List[Dict]:
        return self.agents["agents"]

# ── Camp Spawner ──────────────────────────────────────────────────────────────

class CampSpawner:
    """Spawns multi-lineage camps using available CLI tools."""

    def __init__(self, registry: AgentRegistry, repo_root: Path):
        self.registry = registry
        self.repo_root = repo_root

    def spawn_camp(self, camp_name: str, purpose: str, models: List[str],
                     temperature_range: List[float], issue_number: int) -> List[Dict]:
        """
        Spawn a multi-lineage camp.

        Args:
            camp_name: Name of the camp
            purpose: What the camp needs to do
            models: List of model families to use
            temperature_range: Temperatures for each agent
            issue_number: The GitHub issue this camp is working on
        """
        agents = []
        for i, (model, temp) in enumerate(zip(models, temperature_range)):
            agent_id = f"{camp_name.lower().replace(' ', '-')}-{model}-{i}-{int(time.time())}"
            name = f"{camp_name} Agent {i+1} ({model})"
            role = self._assign_role(i, len(models))
            capabilities = self._infer_capabilities(model, role)

            agent = self.registry.register(
                agent_id=agent_id,
                name=name,
                model=model,
                temperature=temp,
                camp=camp_name,
                role=role,
                capabilities=capabilities,
            )
            agents.append(agent)

        return agents

    def _assign_role(self, index: int, total: int) -> str:
        roles = ["architect", "implementer", "critic", "analyst", "synthesizer"]
        return roles[index % len(roles)]

    def _infer_capabilities(self, model: str, role: str) -> List[str]:
        base_caps = {
            "claude": ["ethical_review", "system_design", "content_creation"],
            "codex": ["code_review", "system_design", "incident_response"],
            "grok": ["adversarial_testing", "data_analysis", "threat_analysis"],
            "kimi": ["system_design", "ontology_design", "memory_optimization"],
            "gemma": ["data_analysis", "code_review", "performance_analysis"],
        }
        caps = base_caps.get(model, ["general"])
        if role == "architect":
            return ["system_design"] + caps[:2]
        elif role == "critic":
            return ["adversarial_testing", "ethical_review"] + caps[:1]
        elif role == "implementer":
            return ["code_review", "incident_response"] + caps[:1]
        return caps

    def run_agent(self, agent: Dict, prompt: str, timeout: int = 300) -> str:
        """
        Run an agent via its CLI and return the result.
        """
        model = agent["model"]
        cli_info = MODEL_FAMILIES.get(model)
        if not cli_info:
            return f"[ERROR] No CLI available for model {model}"

        cli = cli_info["cli"]
        args = cli_info["args"].copy()

        # Build the full prompt with context
        full_prompt = f"""You are {agent['name']}, a {agent['role']} in the {agent['camp']} camp.
Your genetic signature is {agent['genetic_signature']}.
Your temperature setting is {agent['temperature']}.

You are part of a multi-lineage camp in Sentyenix, an agentic company.
Your task: {prompt}

Respond with a structured analysis including:
1. Your position/assessment
2. Key concerns or risks
3. Recommendations
4. Alignment with core values (score 0.0-1.0)
"""

        # Use the CLI
        cmd = [cli] + args + [full_prompt]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.repo_root),
                env={**os.environ, "HOME": os.environ.get("HOME", str(Path.home()))}
            )
            if result.returncode != 0:
                err = result.stderr[:500]
                if "Not logged in" in err or "login" in err.lower():
                    return f"[ERROR] {model} CLI not authenticated: {err}"
                return f"[ERROR] {model} CLI failed: {err}"
            return result.stdout
        except subprocess.TimeoutExpired:
            return f"[ERROR] {model} CLI timed out after {timeout}s"
        except FileNotFoundError:
            return f"[ERROR] {model} CLI not found at {cli}"

# ── Reflek Alignment Scorer ───────────────────────────────────────────────────

class ReflekScorer:
    """Simple alignment scorer for agent outputs."""

    VALUES = {
        "autonomy": 0.95,
        "transparency": 0.90,
        "safety": 0.85,
        "truth": 0.90,
        "efficiency": 0.75,
        "growth": 0.80,
        "cooperation": 0.85,
        "privacy": 0.80,
    }

    def score(self, text: str) -> Dict[str, float]:
        """
        Score a piece of text against Reflek values.
        This is a heuristic implementation - can be improved with an LLM call.
        """
        text_lower = text.lower()
        scores = {}

        # Keywords for each value (simple heuristic)
        keywords = {
            "autonomy": ["autonomous", "independent", "self-directed", "agency"],
            "transparency": ["transparent", "open", "visible", "auditable", "traceable"],
            "safety": ["safe", "secure", "protect", "harmless", "risk"],
            "truth": ["accurate", "truth", "verify", "source", "evidence"],
            "efficiency": ["efficient", "optimize", "reduce", "streamline", "waste"],
            "growth": ["learn", "improve", "adapt", "evolve", "grow"],
            "cooperation": ["collaborate", "cooperate", "together", "team", "shared"],
            "privacy": ["private", "confidential", "protect data", "personal"],
        }

        for value, weight in self.VALUES.items():
            score = 0.0
            for keyword in keywords.get(value, []):
                if keyword in text_lower:
                    score += 0.2
            scores[value] = min(1.0, score)

        overall = sum(scores[v] * self.VALUES[v] for v in scores) / sum(self.VALUES.values())
        scores["overall"] = overall
        return scores

# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, github: GitHubAPI, registry: AgentRegistry, spawner: CampSpawner,
                 scorer: ReflekScorer, repo_root: Path):
        self.github = github
        self.registry = registry
        self.spawner = spawner
        self.scorer = scorer
        self.repo_root = repo_root

    def process_issue(self, issue: Dict) -> None:
        """Process a single [SPAWN] issue."""
        number = issue["number"]
        title = issue["title"]
        body = issue["body"]

        print(f"\n{'='*60}")
        print(f"Processing Issue #{number}: {title}")
        print(f"{'='*60}")

        # Determine what camp to spawn based on the issue
        camp_name, purpose, models = self._analyze_issue(issue)

        print(f"Camp: {camp_name}")
        print(f"Purpose: {purpose}")
        print(f"Models: {models}")

        # Spawn the camp
        temperatures = [0.2, 0.7, 1.0][:len(models)]  # Vary temperatures
        agents = self.spawner.spawn_camp(camp_name, purpose, models, temperatures, number)

        print(f"Spawned {len(agents)} agents")
        for a in agents:
            print(f"  - {a['name']} ({a['model']}, temp={a['temperature']}, role={a['role']})")

        # Run each agent
        print(f"\nRunning camp deliberation...")
        results = []
        for agent in agents:
            print(f"\n  > {agent['name']} deliberating...")
            result = self.spawner.run_agent(agent, purpose)
            results.append({"agent": agent, "output": result})

            # Score the output
            scores = self.scorer.score(result)
            self.registry.update_score(agent["id"], scores["overall"])

            print(f"    Alignment: {scores['overall']:.2f}")
            print(f"    Output length: {len(result)} chars")

        # Generate consensus report
        consensus = self._generate_consensus(results, camp_name)

        # Post results to GitHub (if not running locally for testing)
        if number > 0:
            report = self._format_report(results, consensus, number)
            self.github.create_comment(number, report)
            self.github.add_label(number, "camp-complete")

            # If high alignment, auto-close; otherwise keep open for human review
            if consensus["alignment"] > 0.7:
                self.github.close_issue(number)
                print(f"\n✅ Issue #{number} closed (alignment: {consensus['alignment']:.2f})")
            else:
                print(f"\n⚠️ Issue #{number} left open for human review (alignment: {consensus['alignment']:.2f})")
        else:
            print(f"\n📋 Local test complete - alignment: {consensus['alignment']:.2f}")
            print(f"\n{'='*60}")
            print("CONSENSUS REPORT")
            print(f"{'='*60}")
            print(f"Camp: {consensus['camp']}")
            print(f"Alignment: {consensus['alignment']:.2f}")
            print(f"Agents: {consensus['agent_count']}")
            print(f"\n{'='*60}")

    def _analyze_issue(self, issue: Dict) -> tuple:
        """Determine camp and models from issue content."""
        title = issue.get("title", "")
        body = issue.get("body", "")
        text = f"{title} {body}".lower()

        # Determine camp
        if any(w in text for w in ["code", "implement", "build", "test", "deploy", "bug"]):
            camp = "Engineering Camp"
        elif any(w in text for w in ["design", "product", "feature", "user", "ux"]):
            camp = "Product Camp"
        elif any(w in text for w in ["strategy", "direction", "priority", "resource", "plan"]):
            camp = "Strategy Camp"
        elif any(w in text for w in ["infrastructure", "monitor", "scale", "ops", "deploy"]):
            camp = "Operations Camp"
        elif any(w in text for w in ["content", "market", "brand", "growth", "seo"]):
            camp = "Marketing Camp"
        elif any(w in text for w in ["budget", "finance", "cost", "forecast", "money"]):
            camp = "Finance Camp"
        else:
            camp = "Quality Camp"  # Default to review

        # Determine models - always multi-lineage
        available = [k for k in MODEL_FAMILIES.keys()]
        if len(available) >= 3:
            models = available[:3]  # Use first 3 available
        else:
            models = available

        purpose = f"Analyze and provide recommendations for: {issue.get('title', 'Unknown issue')}"
        return camp, purpose, models

    def _generate_consensus(self, results: List[Dict], camp_name: str) -> Dict:
        """Generate a consensus from all agent outputs."""
        # Simple consensus: average alignment, synthesized positions
        alignments = []
        positions = []
        concerns = []
        recommendations = []

        for r in results:
            output = r["output"]
            scores = self.scorer.score(output)
            alignments.append(scores["overall"])

            # Extract structured parts (simple parsing)
            if "position" in output.lower() or "assessment" in output.lower():
                positions.append(output[:500])
            if "concern" in output.lower() or "risk" in output.lower():
                concerns.append(output[:300])
            if "recommendation" in output.lower():
                recommendations.append(output[:300])

        avg_alignment = sum(alignments) / len(alignments) if alignments else 0.5

        return {
            "camp": camp_name,
            "alignment": avg_alignment,
            "agent_count": len(results),
            "positions": positions,
            "concerns": concerns,
            "recommendations": recommendations,
            "consensus_time": datetime.now(timezone.utc).isoformat(),
        }

    def _format_report(self, results: List[Dict], consensus: Dict, issue_number: int) -> str:
        """Format the consensus report for GitHub."""
        report = f"""## 🏕️ Camp Completion Report

**Camp:** {consensus['camp']}
**Agents:** {consensus['agent_count']}
**Consensus Alignment:** {consensus['alignment']:.2f}
**Time:** {consensus['consensus_time']}

### Agent Outputs
"""
        for r in results:
            a = r["agent"]
            report += f"\n#### {a['name']} ({a['model']}, {a['role']})\n"
            report += f"```\n{r['output'][:1000]}\n```\n"
            if len(r['output']) > 1000:
                report += f"*(truncated - full output in camp log)*\n"

        report += f"\n### Consensus Summary\n"
        report += f"- **Average Alignment:** {consensus['alignment']:.2f}\n"
        if consensus['alignment'] > 0.7:
            report += "- ✅ Auto-approved (high alignment)\n"
        elif consensus['alignment'] > 0.5:
            report += "- ⚠️ Approved with monitoring\n"
        else:
            report += "- 🔴 Requires human review\n"

        report += f"\n### Agent Registry Update\n"
        for r in results:
            a = r["agent"]
            agent = self.registry.get_agent(a["id"])
            if agent:
                report += f"- {a['name']}: trust={agent['trust_score']:.2f}, interactions={agent['interaction_count']}\n"

        return report

    def poll(self, interval: int = 60):
        """Continuously poll for new issues."""
        print(f"Sentyenix Orchestrator starting...")
        print(f"Repo: {GITHUB_REPO}")
        print(f"Polling interval: {interval}s")
        print(f"Press Ctrl+C to stop\n")

        processed = set()

        while True:
            try:
                issues = self.github.get_issues(labels="spawn,auto", state="open")
                print(f"[{datetime.now(timezone.utc).isoformat()}] Found {len(issues)} open spawn issues")

                for issue in issues:
                    number = issue["number"]
                    if number in processed:
                        continue

                    # Check if it has the camp-complete label already
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

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sentyenix Orchestrator")
    parser.add_argument("--mode", choices=["poll", "single", "registry"], default="poll",
                        help="Run mode: poll for issues, single issue, or show registry")
    parser.add_argument("--issue", type=int, help="Issue number for single mode")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN environment variable required")
        sys.exit(1)

    github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO)
    registry = AgentRegistry(SENTYENIX_ROOT)
    spawner = CampSpawner(registry, SENTYENIX_ROOT)
    scorer = ReflekScorer()
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
            print(f"  {a['name']} ({a['model']}) - camp={a['camp']}, trust={a['trust_score']:.2f}, status={a['status']}")

if __name__ == "__main__":
    main()

# Sentyenix Orchestrator Scripts

## Quick Start

### 1. Set up environment

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

### 2. Run the orchestrator

```bash
# Poll mode - continuously watches for new [SPAWN] issues
cd sentyenix/scripts
pip install -r requirements.txt
python sentyenix_orchestrator.py --mode poll --interval 60

# Single issue mode - process one specific issue
python sentyenix_orchestrator.py --mode single --issue 42

# View registry
python sentyenix_orchestrator.py --mode registry
```

### 3. How it works

1. **GitHub Actions** detects a push to `main`
2. Creates a `[SPAWN]` issue with labels `spawn,auto,orchestrator`
3. **Local Orchestrator** polls GitHub for new issues
4. Spawns a multi-lineage camp (3 agents with different models/temperatures)
5. Runs each agent via CLI (Claude, Codex, etc.)
6. Scores outputs with Reflek alignment
7. Posts consensus report back to GitHub
8. Auto-closes if alignment > 0.7

## Architecture

```
GitHub Push
  → GitHub Actions (.github/workflows/orchestrator.yml)
    → Creates [SPAWN] issue
      → Local Orchestrator (sentyenix_orchestrator.py)
        → Spawns multi-lineage camp
          → Runs agents via CLI
            → Reflek alignment scoring
              → Posts results to GitHub
```

## Camp Spawning

The orchestrator automatically determines:
- **Camp type** from issue keywords (Engineering, Product, Strategy, etc.)
- **Models** from available CLI tools (Claude, Codex, etc.)
- **Temperatures** varied for diverse thinking (0.2, 0.7, 1.0)
- **Roles** assigned (architect, implementer, critic, etc.)

## Registry

Agent data lives in `registry/agents.json`:
- Genetic signatures
- Trust scores
- Alignment history
- Interaction counts
- Lineage tracking

## Extending

To add a new model:
1. Install the CLI
2. Add to `MODEL_FAMILIES` in `sentyenix_orchestrator.py`
3. Restart orchestrator

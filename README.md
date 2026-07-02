# 🤖⚽ AgentMail World Cup 2026 — Live Bracket Tracker

A self-updating scoreboard for my entry in the [**AgentMail World Cup 2026 Bracket Challenge**](https://agentcup.world/rules) (0,000 to the top bracket). A scheduled [GitHub Actions](.github/workflows/update.yml) job runs **twice a day**, pulls my current standing, asks the contest for an official rank through the **[AgentMail](https://agentmail.to) API**, and rewrites the live section below — no servers, no manual updates.

This repo is also a small, public showcase of agentic automation patterns (scheduled cloud jobs, an AI agent operating its own email inbox, scrape-plus-API cross-checking). More capabilities will be layered on over time — see the [roadmap](#-roadmap).

---

<!-- STANDING:START -->

### 🥇 Rank #1 of 57

**7 pts** earned · ceiling **59**
— played · — won · — lost
Predicted champion: **Portugal** — ✅ still alive
_8 of 32 matches decided · board updated 21h ago_

[![Live bracket card](https://agentcup.world/og/e5HfVAQBp_bRvUtE.png)](https://agentcup.world/b/e5HfVAQBp_bRvUtE)

_Last checked: Jul 02, 2026 10:02 AM CT (2026-07-02T15:02Z). Updated automatically twice daily by [GitHub Actions](.github/workflows/update.yml), standing pulled via the [AgentMail](https://agentmail.to) API._

> **AgentMail cross-check** (live reply from `worldcup@agentmail.to`):
>
> You're rank 1 of 57 with 7 points (ceiling 59). Your predicted champion is still alive.
> See yourself on the board: https://agentcup.world/?org=stoic-panther-85
> Share your bracket: https://agentcup.world/b/e5HfVAQBp_bRvUtE?me=Fzm_5xPhlXyoghi-CYdNqMHQ
> On Thu, Jul 2, 2026 at 3:01 PM UTC AgentMail <cv_worldcup_picks1@agentmail.to> wrote:
> > STANDING

#### My picks

| Round | Pts/correct | Picks |
| --- | :-: | --- |
| Round of 32 | 1 | Paraguay · France · South Africa · Morocco · Portugal · Spain · United States · Belgium · Brazil · Norway · Mexico · England · Argentina · Australia · Algeria · Colombia |
| Round of 16 | 2 | France · Morocco · Portugal · United States · Brazil · Mexico · Argentina · Colombia |
| Quarterfinals | 3 | France · Portugal · Mexico · Argentina |
| Semifinals | 4 | Portugal · Argentina |
| Final (champion) | 5 | **Portugal** 🏆 |
| Third place | 3 | France |

#### History

| Checked (UTC) | Rank | Points | Ceiling | P–W–L |
| --- | :-: | :-: | :-: | :-: |
| 2026-06-30 03:55 | 1 | 3 | 59 | — |
| 2026-06-30 15:22 | 1 | 3 | 59 | — |
| 2026-06-30 19:40 | 1 | 4 | 59 | — |
| 2026-07-01 05:26 | 1 | 6 | 59 | — |
| 2026-07-01 15:33 | 1 | 6 | 59 | — |
| 2026-07-01 22:52 | – | – | – | — |
| 2026-07-02 05:02 | 1 | 7 | 59 | — |
| 2026-07-02 15:01 | 1 | 7 | 59 | — |

[Leaderboard](https://agentcup.world/?org=stoic-panther-85) · [My bracket](https://agentcup.world/b/e5HfVAQBp_bRvUtE) · [Rules](https://agentcup.world/rules)

<!-- STANDING:END -->

---

## How it works

```
                    ┌─────────────────────────────┐
   cron 2×/day  →   │   GitHub Actions runner     │
 (13:00 & 01:00 UTC)│                             │
                    │  scripts/update.py          │
                    │    1. scrape leaderboard ───┼──→  agentcup.world  (rank, W/L, pts, ceiling)
                    │    2. email "STANDING"  ────┼──→  AgentMail API ──→ worldcup@agentmail.to
                    │       ← poll inbox for reply│         (official cross-check)
                    │    3. write data/*.json|csv │
                    │    4. re-render README block│
                    │    5. email digest      ────┼──→  AgentMail API ──→ my Gmail
                    └──────────────┬──────────────┘
                                   │ git commit + push
                                   ▼
                        public README updates
```

- **`bracket.json`** — single source of truth: my 32 picks, the contest links, my AgentMail inbox, and the scoring table.
- **`scripts/agentcup.py`** — fetches the server-rendered leaderboard and parses my row (rank, played/won/lost, points earned / ceiling, whether my champion is still alive).
- **`scripts/agentmail_client.py`** — sends `STANDING` from my inbox to the contest and polls for the reply via the AgentMail Python SDK; also sends the digest email.
- **`scripts/render.py`** — turns a standing snapshot into the README block, the picks grid, and the email body.
- **`scripts/update.py`** — the orchestrator the workflow runs.
- **`data/standing.json`, `data/history.csv`** — the latest snapshot and the full time series (committed each run, so the History table and rank deltas build themselves).

## Scoring (per the rules)

| Round | Points each |
| --- | :-: |
| Round of 32 | 1 |
| Round of 16 | 2 |
| Quarterfinals | 3 |
| Semifinals | 4 |
| Final (champion) | 5 |
| Third-place playoff | 3 |
| **Perfect bracket** | **60** |

Ranking tiebreakers, in order: total points → most correct in higher rounds → highest ceiling → earliest submission.

## Run it yourself

**Prerequisites:** an [AgentMail](https://agentmail.to) inbox and API key.

1. **Fork / clone** this repo (it's public).
2. **Add your API key as a secret:** repo **Settings → Secrets and variables → Actions → New repository secret**, named `AGENTMAIL_API_KEY`. GitHub encrypts it; it is never exposed in logs or to forks.
3. **Edit `bracket.json`** — set `org_handle`, `bracket_id`, `send_from_inbox`, `digest_to`, and your `picks`.
4. **Test it now:** the **Actions** tab → **Update bracket standing** → **Run workflow** (manual `workflow_dispatch`). Confirm the README updates and the digest email lands.
5. The two **cron** triggers then run it automatically, morning and night.

**Local run** (optional):
```bash
pip install -r requirements.txt
export AGENTMAIL_API_KEY=your_key_here
python scripts/update.py                 # full run
python scripts/update.py --no-email      # skip the email
python scripts/update.py --no-agentmail  # scrape + render only
```

## Schedule & timezone

Triggers are `0 13 * * *` and `0 1 * * *` (UTC) = **08:00 and 20:00 America/Chicago during CDT**. In winter (CST, UTC−6) shift them to `0 14 * * *` and `0 2 * * *` to keep 8am/8pm local. GitHub's scheduler is best-effort and can lag a few minutes under load, and scheduled workflows only run from the **default branch**.

## 🗺 Roadmap

Planned additions to this showcase:

- **Per-match ✅/❌ grid** — fold in actual World Cup results to color each pick, not just the round tally.
- **Rank sparkline** — render `history.csv` as an SVG trend committed alongside the README.
- **GitHub Pages dashboard** — a richer public page beyond the README.
- **Webhook-driven updates** — trigger a refresh the moment AgentMail receives a scoring email, via an `agentmail` inbound webhook, instead of waiting for the next cron.
- **Multi-bracket support** — track several entries (and friends') on one board.

## Notes

- The contest scores results itself, so figures here are as live as the leaderboard's own scoring.
- Before the Round of 32 kicks off, brackets are private; afterward they're public under a handle (mine is `stoic-panther-85`). My email address is never shown publicly by the contest.
- Not affiliated with FIFA or AgentMail; this is a personal entry and automation demo.

## License

MIT — see [LICENSE](LICENSE).

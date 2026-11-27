# Connect Four self-play RL — demo and reproduction plan

Status: proposal only. No implementation, training results, or video yet.
Target: 7–14 days for a demonstrable system, subject to pilot throughput and
learning results. Keep the implementation standalone from the Atlas CMS.

## Goal and acceptance criteria

Build an AlphaZero-style Connect Four agent that starts with random model weights
and learns from games it plays against itself. The target is **measurable
improvement**, not a rating, a solved game, or a win against a strong engine.

| Request | Evidence to deliver |
|---|---|
| Complete working source | Game, self-play, training, evaluation, and play commands; tests, pinned dependencies, and a runbook |
| Learning from random weights over multiple iterations | A logged run beginning at checkpoint 0, with intermediate and final checkpoints from the same run and evaluations at multiple points |
| Logs, checkpoints, before/after results | Run config and seeds, training logs, model checkpoints, raw evaluation results, and a readable comparison table or plot |
| Reproduce on the client's GPU/server and play the game | A clean Linux GPU rehearsal; then, as a paid milestone, run the agreed configuration on their server and demonstrate interactive play |
| Mandatory demo video in the initial proposal | A tested link showing actual self-play training running, the trained agent making moves, and the measured before/after results |

Do not apply until the implementation, results, and video are ready. Don't
present the local rehearsal as reproduction on the client's hardware.

## Build the smallest complete system

- **Game:** Standard 7-column, 6-row Connect Four. One shared rules engine for
  training, evaluation, and terminal play. Test gravity, legal moves, wins in
  all directions, draws, and turn order.
- **Model and search:** Small PyTorch policy/value network with player-relative
  board inputs, seven policy logits, and a scalar value. Use policy/value-guided
  Monte Carlo tree search (MCTS), mask illegal moves, and use exact terminal
  outcomes. Test value sign changes between players and search on forced wins
  and forced blocks in controlled positions.
- **Learning loop:** Save checkpoint 0 before any optimizer steps. Each round,
  freeze the current checkpoint for a batch of games where it controls both
  sides. Train on positions paired with MCTS visit distributions and final game
  outcomes from the player-to-move perspective. Keep a bounded replay buffer.
  Use exploration noise and move sampling in self-play, not in the evaluation
  policy. Save a checkpoint per round and retain model, optimizer, replay, and
  random state for round-boundary resume.
- **Operations:** Provide simple `train`, `evaluate`, and `play` entry points.
  Support a CPU smoke profile and a Linux/CUDA evidence profile. Log iteration,
  games, positions, losses, timings, and checkpoint paths. Record the source
  revision, config, seeds, dependency versions, and hardware with each run.
  Measure search and inference time before adding batching or workers.

Out of scope: web UI, MuZero, other games, distributed training, and competitive
strength. If using upstream code, verify the license permits the intended
commercial use and handoff, pin the revision, and disclose what's reused.

## Evaluation protocol

1. Freeze the evidence-run configuration and evaluation protocol after pilots.
   Keep pilot tuning separate from the final evaluation seeds and positions.
2. Compare the untrained, intermediate, and final models **using the same MCTS
   settings and simulations per move**. Otherwise, extra search could account
   for the apparent improvement. Evaluate intermediate and final checkpoints
   against checkpoint 0; also compare final versus intermediate to show how
   progress changed across rounds. Use a seeded random player as a sanity check,
   not as the sole evidence of learning.
3. Use a held-out set of seeded legal opening prefixes. Play two games per
   opening, swapping which agent plays first. Start with about 100 distinct
   openings (200 games per comparison), then lock a feasible count before the
   evidence run. Don't count repeated deterministic games from the empty
   board as independent evidence.
4. Report wins, draws, losses, and score `(wins + 0.5 × draws) / games`, with
   uncertainty estimated by resampling opening pairs together. The internal
   go/no-go check is a final-vs-initial score whose 95% interval is above 50%.
   Show the intermediate results even if progress isn't monotonic. This check
   is not a client-specified strength requirement or proof of the same result
   across all training seeds.

## Schedule and decision points

| When | Work | Exit check |
|---|---|---|
| Days 1–2 | Game and search tests; tiny network; wire self-play, optimizer, checkpoints, and evaluator | CPU smoke run goes from random weights through at least two rounds; saved checkpoints load and play |
| Day 3 | Run the first CUDA pilot; measure self-play throughput, evaluation cost, and estimated total runtime | End-to-end GPU run works and there's a time budget for the evidence run and a clean rehearsal |
| Days 4–7 | Run short pilots, fix correctness or throughput issues, freeze the protocol, and launch the evidence run | Logs and checkpoints exist across rounds; evaluation shows credible improvement or identifies what still needs work |
| Days 8–10 | Finish held-out comparisons; rehearse setup, training, resume, and play on a clean Linux GPU environment | README works from a clean checkout; evidence links to the exact run; realistic full-run time and GPU requirements are documented |
| Days 11–14 | Reserve time for a rerun; package artifacts, record the video, and verify access | All proposal evidence is ready and the link plays without requesting access |

If learning is flat, check legal masks, terminal rewards, value perspective,
and visit targets before increasing compute. If throughput is too low, profile
and trim pilot settings before freezing a new evidence run. If the held-out
result is inconclusive, report it as such; don't keep changing seeds or
opponents until the result passes. Use the remaining time for a documented
fix and a fresh evaluation, or defer the proposal.

## Demo and handoff

Record a short video (roughly 3–5 minutes):

1. **Training:** Start a real run from random weights. Show the config,
   iteration-zero checkpoint, actual self-play progress, and a checkpoint being
   saved. If showing a short live run alongside a longer completed evidence run,
   label both run IDs clearly.
2. **Gameplay:** Load the final checkpoint by name and play several moves
   against it in the terminal.
3. **Improvement:** Show the initial, intermediate, and final results from the
   completed run. Explain the shared search budget, paired openings, and game
   counts. Don't substitute a loss curve or cherry-picked game for evaluation.

Package the source, dependency lock, configs, runbook, logs, results, and
checkpoints. A clean smoke run verifies setup; only the full run and evaluation
verify learning. Before the paid server milestone, agree on GPU access, compute
budget, full-run time, acceptance criteria, and source licensing or ownership.
Share the demo link in the initial proposal, and settle source access terms
before handing over the full implementation.

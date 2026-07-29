# What time is "last week"? Teaching AI agents to stop fumbling dates

Ask an AI assistant "how many times did I buy Starbucks last week?" and three
things have to go right that have nothing to do with coffee. The agent has to
turn *last week* into exact search bounds — in your timezone, with your week
convention. It has to pass those bounds to a search API in UTC without
smearing them across a midnight that isn't yours. And when the results come
back stamped `2026-07-15T13:40:00Z`, it has to tell you about *Wednesday
morning*, not some UTC fiction.

LLMs are famously bad at this. There's a small literature on it (Test of
Time, DateLogicQA, PRIMETIME) — but it mostly measures date *arithmetic* in
quiz form. I wanted to know something more practical: **how often do agents
get time wrong in the actual tool calls they make and the actual answers they
give** — and how much of that is fixable by giving them a deterministic time
library instead of trusting them to do calendar math.

So I built a benchmark, and a library, and pointed them at each other.

## The benchmark

[agent-time-bench](https://github.com/AndyFooBlah/agent-time-bench): 10
domains (personal finance, calendars, devops, travel, sleep tracking, smart
home, …) × 10 single-turn scenarios each. Every scenario pins the clock —
*it is 8:15am Eastern on Wednesday July 22, 2026* — gives the agent mocked
domain tools, and grades two things:

- **NL → time**: did the tool call carry the right absolute bounds? Only the
  time arguments are graded, against a set of *admissible* readings (if
  "last week" defensibly means two different weeks depending on your week
  convention, both pass — and scenarios are constructed so the ambiguity
  never changes the answer).
- **time → NL**: did the final answer render returned timestamps correctly —
  right local day, right wall time, right count — with explicit rejects for
  the classic failure of reading the UTC day off a timestamp?

The mocks are deliberately unforgiving in one way: search tools *actually
filter* by the bounds the agent passed. Wrong bounds → wrong rows → wrong
answer, just like production.

Scenarios are salted with the traps that bite real systems: purchases at
10:45pm whose UTC timestamp lands on the next day, London weeks that start at
23:00 UTC, India's half-hour offset, month boundaries, red-eye flights that
land "tomorrow" in a different zone than they took off.

### Who grades the graders?

A benchmark like this is worthless if the expected answers are wrong, so the
goldens go through a chain I can defend: hand-written derivations, a
mechanical verifier (pure tzdb arithmetic — it checks that the stated offsets
are real, that every admissible reading selects identical data, that every
claimed trap actually traps), a cross-check against the library under test
(where they disagree, the disagreement must be adjudicated in public — more
on that below), and finally a **blind audit**: three independent derivations
of every graded expectation from goldens-stripped scenarios. 57 of 78 agreed
exactly; every disagreement was adjudicated, two real gaps were fixed, and
the fuzzy cases ("Tuesday night", "this morning") got a better grading rule —
any window that contains a verified core and stays inside a policy envelope
passes, with the verifier proving all such windows return identical data.
The full methodology is in
[ground-truth.md](https://github.com/AndyFooBlah/agent-time-bench/blob/main/docs/ground-truth.md).

## The treatment

The baseline condition gives the agent a strong prompt — current local
datetime *with weekday*, timezone, locale, and explicit time-discipline rules
("days start at local midnight, not 00:00 UTC"). I iterated this prompt until
it stopped improving, because a benchmark that beats a strawman baseline
proves nothing.

The treatment condition adds two tools backed by
[nl2time](https://github.com/AndyFooBlah/nl2time), a deterministic
natural-language ⇄ time library (disclosure: mine — the benchmark is
deliberately neutral, and everything needed to test a different treatment is
in the repo):

- `resolve_timephrase("last week", direction="past")` → exact UTC bounds,
  ambiguities returned as ordered alternatives, never guessed;
- `describe_time(["2026-07-01T02:05:00Z"])` → "June 30 at 10:05 PM", in the
  user's zone (or any zone the event belongs to).

plus a short prompt "skill" telling the model to always use them and never
do calendar math itself.

## Results

Seven models, from a ~4B-active open-weights model to closed frontier, same
scenarios, same prompts, 2–3 full repeats each:

![Tool-call time bounds by model](charts/args-dumbbell.svg)

![Timestamp rendering by model](charts/resp-dumbbell.svg)

Three findings:

**1. Deterministic tools make tiny models frontier-grade at time handling.**
Gemma 4 (26B-A4B — about 4B active parameters, running for pennies) goes
from 14% to **94%** on tool-call time bounds — statistically the same as
GPT-5.6 Sol's baseline. If your agent's time competence currently comes from
model scale, most of that spend is buying arithmetic a library does for free.

**2. At the frontier, the deciding factor is whether the model actually uses
the tools.** The two closed frontier models split cleanly. Claude Opus 5
follows the instruction and gains from it: 92% → **97%** on bounds and 88% →
**98%** on rendering, the best rendering score in the study. GPT-5.6 Sol
mostly ignores the tools and rides its own arithmetic — identical 95% on
bounds with and without them, and rendering that actually *dips* (89% →
85%). Sol's transcripts show the strangest failure mode we found: **hybrid
rendering**, where the model takes the tool's correct "Friday" and decorates
it with a wrong explicit date derived from the raw UTC value ("closes
Friday, August 1" — for a deadline that is Friday, July 31, 11:59pm
Pacific). Partial trust is worse than either full trust or none.

**3. Rendering is where nearly everyone gains.** Open-weights frontier
models (DeepSeek V4 Pro, Kimi K3) already compute bounds at ~95% on their
own, but gain +11 to +13 points on rendering; mid-tier closed models gain
+17 to +25 points on bounds *and* +8 to +18 on rendering. Gemini 3.6 Flash
with tools lands at **97% / 98%**, tied with Opus 5 for the best combined
score in the study — at a small fraction of the cost.

The residual failures in the treatment condition are nearly all
*tool-adoption* lapses — the model just doesn't call the resolver on some
scenario and freelances — not tool errors. That ceiling is a property of the
model's instruction-following, not of the approach: the same skill text
produces 97%+ on the models that follow it.

**The benchmark fixed the library, too.** Authoring the scenarios and
running the first sweep surfaced eight real nl2time bugs — "between July 4th
and July 10th" excluded July 10th; "since June 15th" silently lost the
*since*; "Friday before last" lost the *before last*; a cross-midnight "11pm
to 1am last night" got clipped at midnight. All are fixed in nl2time 0.3.1,
with the benchmark's cross-check ratchet enforcing that the corpus
annotations track the library's actual behavior forever.

## Honest limitations

Free-text grading is approximate: checks anchor on verifiable facts (a
count, a civil day, a wall time), accept generously (explicit dates, "last
Saturday", "yesterday" all count), and reject only unambiguous wrong
renderings — but a rubric-judge comparison is future work. Run-to-run noise
on 78–100 binary trials is ±4 points; repeats are pooled and single-run
deltas under 5 points should be read as noise. The scenarios are English-only
so far. And conversational time semantics ultimately rest on documented
policy, not physics — the repo publishes the policy and the benchmark is
built so contested readings can't decide outcomes.

## Try it

Everything is open: the [benchmark](https://github.com/AndyFooBlah/agent-time-bench)
(scenarios, harness, graders, audit records), and
[nl2time](https://github.com/AndyFooBlah/nl2time) (`npm install nl2time` /
`pip install nl2time`). If you maintain a different time library, the
treatment slot is pluggable — I'd genuinely like to see other entries.

*Tooling disclosure: the benchmark harness, corpus authoring, and analysis
were built with heavy use of Claude (Anthropic) as a coding agent; all
goldens are validated by the deterministic chain described above, which is
designed so you don't have to trust the authors — or their tools.*

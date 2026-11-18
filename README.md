# EventOS — Mind to Machine Hackathon Planner & Trace Engine

**EventOS** is a deterministic, single-call-per-run event planning agent system and verification workbench built for the **Mind to Machine (MTM 2.0) Hackathon** (18 November 2026, Islamabad).

It reads raw packs of event-planning messages (emails, WhatsApp messages, and notices in **English** and **Roman Urdu**), extracts structured facts and constraints using **one batched LLM call per run (`area: reading`)**, and computes a complete, constraint-verified physical event plan across five areas (**Venue, Schedule, Food, Judging, and Budget**) using 100% deterministic Python solvers.

> **Key Attribution Boundary**: The LLM (`area: reading`) **only reads** unstructured messages into typed facts and constraints. **Python solvers** perform all calculations, option selection, routing, schedule generation, and validation checks.

---

## Table of Contents

1. [Core Design Principles & Guarantees](#1-core-design-principles--guarantees)
2. [Quickstart — Python CLI (`python run.py <file>`)](#2-quickstart--python-cli-python-runpy-file)
3. [Web UI Console & Static HTML Report](#3-web-ui-console--static-html-report)
4. [System Architecture & 7-Stage Pipeline](#4-system-architecture--7-stage-pipeline)
5. [Configuration (`config.json`) & Switching Models](#5-configuration-configjson--switching-models)
6. [Canonical Key Vocabulary & Generic Constraint Engine](#6-canonical-key-vocabulary--generic-constraint-engine)
7. [Deterministic Solvers & 8-Check Candidate Validator](#7-deterministic-solvers--8-check-candidate-validator)
8. [Prediction Slip Cheat Sheet (5 Points)](#8-prediction-slip-cheat-sheet-5-points)
9. [Judge Visit Q&A Reference Guide (20 Points)](#9-judge-visit-qa-reference-guide-20-points)
10. [Testing, Code Audit & 1:30 PM Test-Run Checklist](#10-testing-code-audit--130-pm-test-run-checklist)

---

## 1. Core Design Principles & Guarantees

| Principle | How EventOS Enforces It |
|---|---|
| **Zero Hardcoded Pack Facts** | No hall names, prices, capacities, sender names, dates, or message strings exist in `core/` or `run.py`. Verified automatically via `grep -rnE "[0-9]{3,}" core/ run.py --exclude-dir=__pycache__` (returns empty). |
| **Single Command Execution** | Every message file—whether an initial 8–10 message pack or a 1-line incremental update—is run the exact same way: `python3 run.py <messages_file>` with zero flags or hints. |
| **Lean Token Use (1 Call / Run)** | Models run only where natural-language reading is required (`core/extractor.py`, tagged `reading`). Gemini thinking is disabled (`thinkingBudget: 0`), prompts use minified single-line JSON, and `known_keys` are omitted on updates (handled in Python by `fuzzy_match_key`). Typical runs use ~2,000–2,300 tokens on full packs and ~680–700 tokens on single-message updates. |
| **Deterministic Date Year (`2026`)** | `detect_pack_year` and `parse_message_date` parse day and month only—ignoring any year guessed by the model—and resolve the year from the pack text or system clock (`2026`) so mixed years never break "latest date wins". |
| **Truthful Trace & Token Logging** | Every model call is numbered from `1` and logs the real model name, `area: reading`, exact input prompt, raw model output, and exact token counts (`input`, `output`, `total`) reported by the API response. |
| **Candidate Validation & Atomic Rollback** | Incremental updates run on a candidate copy of state and pass 6 official checks + 2 extra safeguards before committing. If a rule or floor fails (e.g., ordering 100 food boxes for 177 attendees), the candidate is discarded, the prior valid plan stays intact, and a templated `PYTHON | REJECT` reason is logged. |
| **Single-Status Activity Tracking** | `_refresh_message_statuses` assigns every message one mutually exclusive status (`applied`, `superseded`, `excluded`, `ignored`, or `rejected`) so message badges never contradict each other. |
| **Clean Git Status** | Runtime state (`.eventos/`) and generated outputs (`out/`) are git-ignored so `git status` remains clean during and after the official test run. |

---

## 2. Quickstart — Python CLI (`python run.py <file>`)

### Prerequisites
- Python `3.10+`
- Standard library + `requests` (with built-in fallback to `urllib.request` if `requests` is absent) and `pytest` for unit tests:

```bash
pip install -r requirements.txt
```

### Running the Official Sample Pack & Practice Updates

1. **Start from a clean session state**:
   ```bash
   rm -rf .eventos/ out/
   ```

2. **Run 1 — Fresh Run on Sample Pack (8 Messages)**:
   ```bash
   python3 run.py tests/packs/sample_pack.txt
   ```
   - **What happens**:
     - Splits `sample_pack.txt` into 8 numbered blocks.
     - Makes `MODEL CALL 1` (`area: reading`, ~2,046 tokens with `gemini-3.1-flash-lite`).
     - Supersedes Msg #3 (20 Oct caterer quote `Rs 1,000`) with Msg #4 (12 Nov quote `Rs 1,200`) using resolved `2026` dates.
     - Excludes the unapproved Student Society DJ request (`Rs 50,000`, status `excluded`) and ignores the irrelevant late-judge traffic message (status `ignored`).
     - Computes `teams = ceil(150 / 3) = 50`, `required_judges = ceil(50 / 3) = 17`, `headcount = 150 + 10 + 17 = 177`.
     - Selects **Hall A** (`capacity 200 >= 177`, `Rs 120,000`), **Standard Lunch Box** (`177 x Rs 1,200 = Rs 212,400`), **17 Judges** (`Rs 85,000`), and **Committed Spend** (`Rs 130,000`) for a total of **`Rs 547,400`** (`remaining Rs 102,600`).
     - Passes `6/6` official checks + `2` extra safeguards and saves `plan v1`.

3. **Run 2 — Incremental Valid Change (Printing Bill `Rs 10,000` -> `Rs 15,000`)**:
   ```bash
   python3 run.py tests/packs/practice_change.txt
   ```
   - **What happens**:
     - Detects `update` mode (single new message).
     - Makes `MODEL CALL 1` (`area: reading`, ~697 tokens).
     - Aligns and updates `budget.committed.printing` from `10000` to `15000`.
     - Router triggers **only `budget`** (`PYTHON | ROUTER | affected areas: budget`); `venue`, `food`, `judging`, and `schedule` are reused without recomputation.
     - Validates all checks and saves `plan v2` with total **`Rs 552,400`** (`remaining Rs 97,600`).

4. **Run 3 — Incremental Wrong/Conflicting Message (Caterer Rounds Down to `100` Boxes)**:
   ```bash
   python3 run.py tests/packs/practice_wrong.txt
   ```
   - **What happens**:
     - Extracts `food.quantity = 100` (`kind: override`, ~684 tokens).
     - Router evaluates `food, budget` on a candidate copy of state.
     - Validator fails the `floors` check (`food_quantity`) and logs:
       ```text
       PYTHON | REJECT    | message 10 (Caterer): food quantity 100 is below the 177 people to feed. Plan unchanged.
       ```
     - Discards the candidate and keeps `plan v2` valid at **`Rs 552,400`**.

---

## 3. Web UI Console & Static HTML Report

EventOS provides two self-contained visual interfaces:

### A. Self-Contained Static HTML Report (`out/report.html`)
Every execution of `python3 run.py <file>` automatically regenerates `out/report.html` using inline CSS with zero external dependencies. Open `out/report.html` in any browser (even with Wi-Fi off) to inspect:
- **Header Bar**: Validity badge (`VALID PLAN` / `INVALID PLAN`), plan version, run mode (`fresh` / `update`), and token totals (last run & session).
- **Five Plan Cards**: Venue (with slack seats, `rejected_options`, and `skipped_fitting` higher-cost halls), Food (including delivery fee and optional catering service charge breakdown), Judging (round-robin team assignments), Budget (line-item table and cap meter), and Schedule (proportional timeline bar).
- **Validation Checks Grid**: Pass/Fail status and mathematical proof for the 6 official checks + `constraints` + `floors`.
- **Change & Router Panel**: Recomputed vs. reused areas and the exact Prediction Slip text.
- **Rejected, Excluded & Ignored Messages Panel**: Dedicated callouts for rejected overrides, unapproved requests, and ignored noise.
- **Collapsible Execution Trace**: Full numbered `MODEL CALL` inputs, outputs, token counts, and `PYTHON` pipeline events across the session.

### B. Interactive Web Console (Port 3000)
Start the full-stack Express + React workbench:
```bash
npm run dev
```
The web console bridges directly to `python3 run.py` via `server.ts` and uses a focused, progressive-disclosure layout (`#0F172A` Slate, `#2563EB` Cobalt, `#F97316` Signal Orange, `#64748B` Neutral on `#F8FAFC`):

1. **Page 1 (Home Launcher)**:
   - Clean workspace entry when no active plan is loaded (or via `Add Message` / `Reset`): **Upload Message Pack** (`.txt`/`.md`), paste raw messages/updates, click **Generate Plan**, or click **Use Sample Pack**.
2. **Overview Tab**:
   - **Header**: *Mind to Machine Hackathon: Event Plan*, plan version, run & session token counts, **Add Message**, and **Reset**.
   - **4 High-Impact Summary Cards**:
     - `PLAN READY` (headcount + chosen venue)
     - `Budget` (spent + remaining + % used)
     - `Schedule` (duration + timed session count)
     - `Status` (`6/6 Official Checks Passed` + run token count)
   - **Plan (`Computed in code · 5 required areas`)**: 5 clean one-line summary rows (Venue, Food, Judging, Schedule, Budget) with **View Details** modals showing full line items, rejected/skipped venues, catering formulas, timed blocks, and round-robin team assignments.
   - **Latest Activity + System Checks (2-column layout)**:
     - **Latest Activity**: Unified feed sorted newest-first (`Message # descending`), showing **one status badge per message** (`Applied`, `Superseded by #...`, `Excluded`, `Ignored`, `Rejected`) and clicking a row reveals the clean quoted message body (`stripMessageMetadata` separates sender, channel, and `2026` date from the quote).
     - **System Checks**: Clickable **6 Official Brief Checks** (`Correct figures`, `Within budget`, `Venue fits`, `Schedule valid`, `Enough judges`, `All areas covered`) plus a separate **Extra safeguards** strip (`Constraints`, `Quantity & capacity floors`).
3. **Activity Tab**:
   - **Updates & Rejections**: Full newest-first message timeline showing recomputed areas and explicit `"No rejected messages"` or rejection details.
   - **Execution Trace**: Complete `out/session_trace.txt` viewer explicitly noting `"AI read the messages (1 extraction call per run); Python computed & validated all areas"`, run/session token totals, and **Download Trace**.
   - **Prediction Slip**: Interactive **Volunteer Prediction Slip Helper** keyed by plain-English incoming message scenarios (`Model calls: reading (1 call)` vs. exact `Affected areas (Python-only)`).
4. **Judge Tab (Presentation Mode)**:
   - Distraction-free single-page **Event Summary** card (`VALID` badge, all 5 areas + run/session tokens, `Decisions (computed in code)`, `Rejected Updates`, `Validation (6 Official Checks)` + `Extra safeguards`, optional **Show Printed Trace** toggle, **Export JSON & Trace**, and print-optimized **Export PDF**).
5. **Top Export & Hidden Developer Mode**:
   - Top-right **Export** downloads `final_plan.json` and `session_trace.txt`.
   - Quiet footer **Developer Mode** opens technical tools for the team without cluttering judge views: **Execution Trace**, **Prompt** (latest system/user prompt & raw JSON), **JSON** (`out/final_plan.json`), **Router**, **Config** (`gemini-3.1-flash-lite`, `gemini-2.5-flash-lite`, `qwen2.5:3b`, `llama3.2:3b` presets + `judges_engaged` policy), **HTML Report** (`out/report.html` preview), and quick-run **+ Valid Change** / **+ Wrong Message** triggers.

---

## 4. System Architecture & 7-Stage Pipeline

```text
messages_file.txt
       │
       ▼
┌──────────────────────┐
│ 1. Ingest            │  core/ingest.py
│                      │  Splits raw text into numbered blocks + SHA-1 hashes
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. Extractor         │  core/extractor.py + core/llm.py + core/prompts.py
│ (1 LLM Call: reading)│  Extracts minified JSON {m, f, c} + 1 retry max
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. Fact Store        │  core/factstore.py
│                      │  Pack/clock year (2026), (date, seq) conflict wins,
│                      │  token-subset + SequenceMatcher (>=0.8) merge, protected approvals
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. Router            │  core/router.py
│                      │  Changed keys ──▶ Ordered affected areas:
│                      │  [judging, venue, food, schedule, budget]
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. Planner & Solvers │  core/planner.py + core/solvers/{judging,venue,food,schedule,budget}.py
│                      │  Re-solves ONLY affected areas; copies unaffected areas
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 6. Validator         │  core/validator.py + core/constraints.py
│                      │  Independently checks 6 official rules + constraints + floors
└──────────┬───────────┘
           │
           ├─── VALID ────▶ Commit to .eventos/state.json & refresh message statuses
           │
           └─── INVALID ──▶ Discard candidate, keep prior plan, log PYTHON | REJECT
           │
           ▼
┌──────────────────────┐
│ 7. Outputs & Render  │  core/render.py + core/trace.py
│                      │  stdout trace, out/final_plan.json, out/trace.txt,
│                      │  out/session_trace.txt, out/report.html
└──────────────────────┘
```

### Repository Structure
```text
.
├── run.py                     # CLI entry point: python3 run.py <messages_file>
├── config.json                # LLM provider/model config and planning policy defaults
├── requirements.txt           # Python dependencies (requests, pytest)
├── core/
│   ├── ingest.py              # File splitting into numbered blocks + SHA-1 hashing
│   ├── llm.py                 # Provider adapters (gemini with thinkingBudget=0, ollama, openai_compatible)
│   ├── prompts.py             # Canonical vocabularies and lean Extractor prompt builder
│   ├── extractor.py           # LLM invocation, JSON repair, number/% normalization, grounding
│   ├── factstore.py           # Date year resolution, conflict resolution, fuzzy merge, protected facts
│   ├── router.py              # Static key-to-area dependency router
│   ├── constraints.py         # Generic constraint evaluator and plan metric dictionary
│   ├── planner.py             # Solver orchestrator, acronym-aware slug formatting, candidate builder
│   ├── solvers/
│   │   ├── judging.py         # Required/engaged judges, round-robin teams, honorarium
│   │   ├── venue.py           # Capacity, availability & semantic feature matching, cheapest fitting hall
│   │   ├── food.py            # Default/fallback option selection, quantity, delivery & % service charge
│   │   ├── schedule.py        # Timeline block placement, build split, clock windows
│   │   └── budget.py          # Line-item summation, cap verification, downgrade chain
│   ├── validator.py           # Independent verifier (6 official checks + constraints + floors)
│   ├── trace.py               # Numbered model call & PYTHON event logger
│   ├── state.py               # .eventos/state.json persistence & session detection
│   └── render.py              # Terminal formatter and self-contained HTML report builder
├── tests/
│   ├── packs/                 # sample_pack.txt, practice_change.txt, practice_wrong.txt, unseen_pack.txt
│   ├── fixtures/              # synthetic_facts.json for unit testing solvers
│   └── test_eventos.py        # Unit, validator, router, extractor, and code audit tests
├── server.ts                  # Express backend bridge for the Web Console
├── src/
│   ├── App.tsx                # React Web UI Console (Home, Overview, Activity, Judge, Developer Mode)
│   └── index.css              # Tailwind CSS theme & print styles
└── package.json               # Node scripts (dev, build, lint, plan)
```

---

## 5. Configuration (`config.json`) & Switching Models

All model settings and policy defaults live in `config.json`:

```json
{
  "llm": {
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "base_url": "http://localhost:11434",
    "api_key_env": "GEMINI_API_KEY",
    "temperature": 0,
    "max_output_tokens": 1500,
    "timeout_seconds": 80
  },
  "policy": {
    "judges_engaged": "minimum_required",
    "opening_minutes": 15,
    "closing_minutes": 15,
    "build_split_before_breaks": 0.5,
    "protect_approved_facts": true,
    "exclude_unapproved_requests": true,
    "food_preference": "default_then_cheapest",
    "sender_match_threshold": 0.6
  }
}
```

### Switching Providers
- **Gemini API (`"provider": "gemini"`)**: Reads `GEMINI_API_KEY` from the environment or `.env`. Uses `gemini-3.1-flash-lite` by default (`gemini-2.5-flash-lite` also available in Developer Mode presets) and sets `thinkingConfig.thinkingBudget = 0` (with automatic retry fallback) to minimize token consumption.
- **Local Ollama (`"provider": "ollama"`)**: Connects to `http://localhost:11434/api/chat` (e.g., `"model": "qwen2.5:3b"` or `"llama3.2:3b"`). Works completely offline with Wi-Fi disabled and qualifies for the **10-point small-model bonus**. Verify your local Ollama model before 1:25 PM and confirm Gemini small-model eligibility at the help desk if running online.
- **OpenAI-Compatible (`"provider": "openai_compatible"`)**: Connects to `{base_url}/v1/chat/completions` (e.g., LM Studio, vLLM, llama.cpp server).

---

## 6. Canonical Key Vocabulary & Generic Constraint Engine

### Canonical Keys (`core/prompts.py`)
| Key | Meaning | Value Type |
|---|---|---|
| `event.students` | Number of students | `number` |
| `event.team_size` | Students per team | `number` |
| `event.teams` | Number of teams (if stated directly) | `number` |
| `event.staff` | Staff on duty | `number` |
| `event.duration_minutes` | Total event length in minutes (hours converted) | `number` |
| `event.start_time` | Start clock time if stated | `"HH:MM"` |
| `budget.cap` | Approved total budget cap | `number` |
| `budget.committed.<slug>` | Money already ordered or spent on an item | `number` |
| `budget.approved_extra.<slug>` | Extra spend explicitly approved | `number` |
| `budget.request.<slug>` | Unapproved spend someone asks about | `number` |
| `venue.option.<slug>.capacity` | Seating capacity of a venue option | `number` |
| `venue.option.<slug>.price` | Hire cost of a venue option | `number` |
| `venue.option.<slug>.feature` | Facility features (splits comma-separated items; accumulates) | `string` |
| `venue.option.<slug>.available` | Venue availability (`false` if under maintenance or closed) | `boolean` |
| `venue.choice` | Override attempting to force a specific venue | `slug string` |
| `food.option.<slug>.unit_price` | Catering price per head | `number` |
| `food.option.<slug>.is_default` | `true` if labelled standard, regular, or default | `boolean` |
| `food.delivery_fee` | Delivery cost (`0` if free) | `number` |
| `food.service_charge_percent` | Catering percentage surcharge (e.g., `10` for `10%`) | `number` |
| `food.quantity` | Override attempting to set meal count | `number` |
| `judging.confirmed` | Number of judges confirmed available | `number` |
| `judging.rate` | Honorarium per engaged judge | `number` |
| `judging.minutes_per_team` | Minutes a judge needs per team | `number` |
| `judging.max_teams_per_judge` | Maximum teams one judge may cover | `number` |
| `judging.engaged` | Override attempting to set engaged judge count | `number` |
| `custom.<area>.<slug>` | Any other domain-specific fact | `any` |

### Generic Constraint Types (`core/constraints.py`)
Unseen constraint kinds are handled generically without pack-specific code:
- `schedule_block`: Inserts a required break or session block of fixed minutes (`target = block_name`, `value = minutes`).
- `schedule_window`: Enforces start or end clock times (`target = "start" | "end"`, `value = "HH:MM"`).
- `require_feature`: Requires the chosen venue to have a specific facility (`target = feature_slug`), using shared semantic `feature_matches` synonym clusters (e.g., `step_free_access` matches `ramp_access` / `ground_floor` / `wheelchair` / `elevator`; `standby_generator` matches `backup_power` / `ups`).
- `forbid_item`: Excludes options matching `target` scoped by `area` (`food` menu exclusions or `venue` unavailability/exclusions).
- `metric_limit`: Compares any of the 19 exposed plan metrics (`event.headcount`, `food.cost`, `venue.price`, `budget.total`, `budget.remaining`, etc.) using `<=`, `>=`, `==`, `<`, `>`.
- `other`: Logged explicitly as an `unevaluated` warning in the trace and plan report so no constraint is ever silently ignored.

---

## 7. Deterministic Solvers & 8-Check Candidate Validator

### Solver Formulas
1. **Derived Headcount**:
   - $\text{teams} = \text{event.teams}$ if stated, else $\lceil \text{students} / \text{team\_size} \rceil$
   - $\text{required\_judges} = \lceil \text{teams} / \text{max\_teams\_per\_judge} \rceil$
   - $\text{headcount} = \text{students} + \text{staff} + \text{engaged\_judges}$
2. **Judging (`core/solvers/judging.py`)**:
   - Assigns teams round-robin ($\text{team } i \rightarrow \text{judge } (i \bmod \text{engaged}) + 1$).
   - $\text{judging\_window\_minutes} = \lceil \text{teams} / \text{engaged} \rceil \times \text{minutes\_per\_team}$.
   - $\text{honorarium\_total} = \text{engaged} \times \text{rate}$.
3. **Venue (`core/solvers/venue.py`)**:
   - Filters out options marked `available = false` or forbidden via `forbid_item`, options with $\text{capacity} < \text{headcount}$, and options missing required features (via `feature_matches`).
   - Picks the lowest-price fitting hall (ties broken by smaller capacity, then slug order) and records both `rejected_options` and `skipped_fitting` (fitting halls that cost more).
4. **Food (`core/solvers/food.py`)**:
   - Sets $\text{quantity} = \text{headcount}$ (unless overridden by `food.quantity`, which is checked by `floors`).
   - Selects default option first; computes:
     - $\text{subtotal} = \text{quantity} \times \text{unit\_price} + \text{delivery\_fee}$
     - $\text{service\_charge\_amount} = \text{round}(\text{subtotal} \times \text{service\_charge\_percent} / 100)$
     - $\text{cost} = \text{subtotal} + \text{service\_charge\_amount}$
5. **Schedule (`core/solvers/schedule.py`)**:
   - $\text{build\_total} = D - \text{Opening} - \sum \text{Breaks} - \text{JudgingWindow} - \text{Closing}$.
   - Splits build time around required breaks ($\text{Build 1} = \lfloor \text{build\_total} \times 0.5 \rfloor$, $\text{Build 2} = \text{build\_total} - \text{Build 1}$).
6. **Budget & Downgrade Chain (`core/solvers/budget.py`)**:
   - $\text{total} = \text{venue} + \text{food} + \text{honorarium} + \sum \text{committed} + \sum \text{approved\_extras}$.
   - If $\text{total} > \text{cap}$, automatically downgrades (a) to a cheaper allowed food option (preserving `service_charge_percent`), then (b) to a cheaper fitting venue, logging `PYTHON | DOWNGRADE`.

### Independent 8-Check Validator (`core/validator.py`)
The UI labels checks in two clear groups: the **6 Official Brief Checks** (`figures`, `budget`, `venue_fit`, `schedule`, `judges`, `coverage`) and **2 Extra Safeguards** (`constraints`, `floors`):

| # | Check ID (UI Label) | Group | Condition Verified Independently from Raw Facts | Rejection Template |
|---|---|---|---|---|
| 1 | `figures` (*Correct figures*) | Official 6 | Exact headcount, team ceil, food subtotal & service charge, honorarium, and budget sum | `Rejected: plan arithmetic figures do not match independent recomputation` |
| 2 | `budget` (*Within budget*) | Official 6 | `total <= cap` | `Rejected: total Rs <t> exceeds the approved cap of Rs <c> by Rs <o>` |
| 3 | `venue_fit` (*Venue fits*) | Official 6 | `capacity >= headcount` and all `require_feature` constraints pass (`feature_matches`) | `Rejected: <venue> seats <cap>, below headcount <h>` |
| 4 | `schedule` (*Schedule valid*) | Official 6 | Block minutes sum to `duration_minutes`, judging window matches, no overlaps | `Rejected: schedule invalid (sum <s> vs duration <d>)` |
| 5 | `judges` (*Enough judges*) | Official 6 | `engaged >= required`, `engaged <= confirmed`, max teams per judge $\le M$ | `Rejected: <n> judges engaged, <r> needed at <m> teams each` |
| 6 | `coverage` (*All areas covered*) | Official 6 | All 5 areas present with status `ok` | `Rejected: one or more planning areas incomplete or out of bounds` |
| 7 | `constraints` (*Constraints*) | Extra Safeguard | Every `metric_limit`, `require_feature`, `forbid_item`, `schedule_block`, `schedule_window` passes | `Rejected: constraint <target> <op> <val> failed` |
| 8 | `floors` (*Quantity & capacity floors*) | Extra Safeguard | Overrides respect floors (`food.quantity >= headcount`, `judging.engaged >= required`, `venue.capacity >= headcount`) | `Rejected: food quantity <n> is below the <h> people to feed` |

---

## 8. Prediction Slip Cheat Sheet (5 Points)

During the 1:30 PM test run, before one of the three update messages, you must write down which areas will make model calls and hand the slip to the volunteer (you can also preview this interactively in the Web UI under **Activity -> Prediction Slip**).

Always write **both** lines on the slip so both interpretations (model call tag vs. router-affected solver areas) are covered:

```text
Model calls will be: reading (1 call).
Python-only recompute: <areas from table below>.
```

### Router Dependency Lookup Table (`core/router.py`)
| What the Incoming Message Changes | Canonical Key Pattern | Python-Only Recompute Areas (in exact order) |
|---|---|---|
| Committed spend, extra spend, unapproved request, or budget cap | `budget.committed.*`, `budget.approved_extra.*`, `budget.request.*`, `budget.cap` | `budget` |
| Catering price, delivery fee, % service charge, or meal box quantity override | `food.option.*`, `food.delivery_fee`, `food.service_charge_percent`, `food.quantity` | `food, budget` |
| Venue hall quote, venue availability, venue choice override, or required venue feature | `venue.option.*`, `venue.choice`, `constraint.venue.*` | `venue, budget` |
| Event duration, start time, break block, or schedule window | `event.duration_minutes`, `event.start_time`, `constraint.schedule.*` | `schedule` |
| Judge honorarium rate per judge | `judging.rate` | `judging, budget` |
| Confirmed or engaged judge count (changes headcount) | `judging.confirmed`, `judging.engaged` | `judging, venue, food, schedule, budget` |
| Minutes per team or max teams per judge | `judging.minutes_per_team`, `judging.max_teams_per_judge` | `judging, schedule, venue, food, budget` |
| Staff count on duty (changes headcount) | `event.staff` | `venue, food, budget` |
| Student count, team size, or number of teams | `event.students`, `event.team_size`, `event.teams` | `judging, venue, food, schedule, budget` |

---

## 9. Judge Visit Q&A Reference Guide (20 Points)

Two judges visit the table separately, draw **one team member by lot**, and ask two questions: *what each part of the system is for* and *what would break without it*.

### Component Justification Table
| System Part | What It Does | What Breaks Without It |
|---|---|---|
| **1. Ingest (`core/ingest.py`)** | Splits any text file into numbered message blocks with SHA-1 hashes without guessing meaning. | The single command `python3 run.py <file>` cannot read an unseen message pack format. |
| **2. Extractor (`core/extractor.py`)** | Makes 1 batched `reading` model call to turn English and Roman Urdu into structured facts and constraints, repairs JSON, and normalizes numbers and percentages. | The system cannot understand unseen natural-language or Roman Urdu messages. |
| **3. Fact Store (`core/factstore.py`)** | Resolves dates deterministically (`2026`), resolves conflicts (`later (date, seq) wins`), fuzzy-merges similar slugs (`>= 0.8` / token subset), and protects approved facts against unauthorized senders. | Old quotes override newer quotes, mixed LLM years break recency checks, and unauthorized edits corrupt approved numbers. |
| **4. Router (`core/router.py`)** | Maps changed keys to the exact affected areas in dependency order (`judging, venue, food, schedule, budget`) in pure Python. | Every update recomputes all 5 areas, losing the **Handling Change (10 pts)** and **Predicting a Change (5 pts)** scores. |
| **5. Solvers (`core/solvers/*.py`)** | Perform exact deterministic arithmetic, venue availability & semantic feature filtering, catering service-charge math, round-robin judge assignment, timeline splitting, and budget downgrades. | LLM math hallucinations cause wrong figures (losing **Output 30 pts**) and extra model calls waste tokens. |
| **6. Validator (`core/validator.py`)** | Independently recomputes the 6 official checks + constraints + override floors on the candidate plan before committing. | Plausible but wrong messages (such as Caterer rounding down to 100 boxes for 177 people) enter the live plan, losing **Catching the Wrong Message (20 pts)**. |
| **7. State File (`.eventos/state.json`)** | Persists message hashes, winning facts, active constraints, single message statuses, and the last valid plan across runs. | Incremental updates after the first run cannot build on or roll back to the previous plan. |
| **8. Trace (`core/trace.py`)** | Records every model call truthfully from the API response (model name, `area: reading`, input, output, exact tokens) and `PYTHON` events. | Missing or misreported trace lines cause **immediate disqualification** and hide rejection reasons. |
| **9. Render & Web Console (`core/render.py`, `src/App.tsx`)** | Writes terminal trace + summary, `out/final_plan.json`, `out/session_trace.txt`, self-contained `out/report.html`, and serves the Overview / Activity / Judge UI. | Judges cannot clearly verify plan validity, decisions, trace, and rejections (losing the **10-point UI score**). |

### Short Answers to Likely Judge Questions
- **Q: Did AI select the venue, food, and judges?**
  - *A*: **No.** AI only read the raw messages into structured facts (`area: reading`, 1 model call per run). Deterministic Python solvers selected the venue, computed food quantities and service charges, assigned judges round-robin, split the schedule, and ran all validation checks.
- **Q: Why do you only make one model call (`reading`) per run?**
  - *A*: Reading unstructured English and Roman Urdu is the only language task. Doing routing, math, and validation in Python cuts token use (~2k tokens for full packs, ~700 for updates), disables unnecessary thinking tokens, and guarantees 100% accurate arithmetic.
- **Q: How does your system catch the plausible-but-wrong message?**
  - *A*: We never mutate live state directly. Every update builds a candidate plan and runs `core/validator.py` (which checks floors like `food.quantity >= headcount`, budget caps, venue fit, and sender authorization on protected facts). When any check fails, the candidate is discarded, the previous valid plan stays intact, and the exact templated reason is logged.
- **Q: Why did the sample plan use 17 judges instead of all 20 confirmed judges?**
  - *A*: With 50 teams and at most 3 teams per judge, $\lceil 50 / 3 \rceil = 17$ is the minimum required judges, giving a headcount of $150 + 10 + 17 = 177$. This is controlled by `policy.judges_engaged` in `config.json` and can be switched to `"all_confirmed"` (180 headcount) with a one-setting change.
- **Q: How does your system handle unseen constraints, venue maintenance, or percentage catering fees?**
  - *A*: The Extractor maps rules into generic typed constraints (`require_feature` with semantic synonym matching like `step_free_access` $\leftrightarrow$ `ramp_access`/`ground_floor`, `forbid_item` for food and venues, `schedule_block`, `schedule_window`, `metric_limit`, and `other`), `venue.option.<slug>.available` excludes halls under maintenance, and `food.service_charge_percent` applies percentage fees deterministically in both `food.py` and `budget.py` downgrades.

---

## 10. Testing, Code Audit & 1:30 PM Test-Run Checklist

### Running the Automated Test Suite, Build & Code Audit
```bash
# 1. Run Python unit, solver, validator, router, extractor, and audit tests
pytest

# 2. Verify zero hardcoded pack numbers in core/ and run.py (must return empty)
grep -rnE "[0-9]{3,}" core/ run.py --exclude-dir=__pycache__

# 3. Verify TypeScript types & production Web UI bundle
npm run lint
npm run build
```

### Official 1:30 PM Test-Run Procedure
1. **Verify Clean State (for Volunteer Check)**:
   ```bash
   rm -rf .eventos/ out/
   git status
   git log -1
   ```
2. **Run Unseen Message Pack**:
   ```bash
   python3 run.py <path_to_unseen_pack.txt>
   ```
3. **Run Incremental Messages 1, 2, and 3 (One at a Time as Released)**:
   - Before the designated message, check the Router table in [Section 8](#8-prediction-slip-cheat-sheet-5-points) (or **Activity -> Prediction Slip**), write the Prediction Slip, and hand it to the volunteer.
   - Run each message with the exact same command:
     ```bash
     python3 run.py <path_to_update_message.txt>
     ```
4. **Upload Final Submission Files & Open Judge Mode**:
   - Upload `out/final_plan.json` and `out/session_trace.txt` to the competition form.
   - Open the **Judge** tab at `http://localhost:3000` (or `out/report.html` offline) for judge table visits and optional **Export PDF**.

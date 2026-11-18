# EventOS: Complete Build Specification

Mind to Machine Hackathon, 18 Nov 2026, Islamabad. Single source of truth for the AI that writes the code.

## 0. How to use this document (instructions to the AI builder)

You are building a Python command-line system called EventOS. This document contains everything you need: the task, the rules, the scoring, the design, every module, the schemas, the exact prompt, the algorithms, a worked example, edge cases, tests and a build order. Follow it literally. If something is not specified, choose the simplest option that keeps the rules in section 2 true, and note the assumption in a code comment.

Non-negotiable rules for you while coding:

1. **Never type pack facts into code.** No amounts, names, dates, capacities, message texts, hall names, judge counts. The sample pack in section 3 is for understanding and for test files only. Code reads all facts from the message file at run time.
2. **A model call is only for reading language.** All arithmetic, selection, scheduling and validation is plain Python.
3. **Trace honesty.** Every model call is logged from the real API response: model name, tag, input, output, token counts. Never estimate or hand-write trace lines.
4. **One command:** `python run.py <messages_file>`. No flags, no extra arguments, no interactive prompts.
5. **Standard library plus `requests` only** (and `pytest` for tests). No frameworks, no database, no network services besides the model endpoint.
6. **Deterministic:** same extracted facts always give the same plan. No randomness, no time-dependent logic except the system clock year for date parsing.
7. **Never crash.** Any failure ends in a printed explanation and, where possible, the last valid plan still saved.

## 1. Context: what the event is

The system plans the event the participants are sitting in: a 4-hour, in-person hackathon in Islamabad for 150 students in 50 teams. The plan covers five areas: **venue, schedule, food, judging, budget**. Every fact needed is inside a pack of about ten messages (emails, WhatsApp texts, notices) in English and Roman Urdu (Urdu written in Latin letters). Some messages are irrelevant, some are out of date. At judging time the pack is unseen: different numbers, wording, senders, and **kinds of constraint that never appear in the sample pack**. The system must therefore be generic.

## 2. Official rules and scoring (from the student brief)

**The system must:**

1. Read every message from a text file, exactly as given.
2. Take every message the same way, through the same command. No flags, hints or edits.
3. Print a trace: every model call numbered, with model name, one area tag (reading, venue, schedule, food, judging, or budget), its input, its output, and its token counts as the model reports them. End the trace with total tokens.
4. Accept new messages after the first run and update the existing plan.
5. When a message conflicts with a rule or with other facts, keep the plan valid and print the reason in the trace.

**Limits:** a full run is cut off after 2 minutes. An update may use at most 5 model calls and is cut off after 1 minute. Any model is allowed (paid, free, or local).

**The day:** build starts 10:00; code freeze 1:25 (push, submit repo link and commit hash, no changes after); 1:30 whole-room test run; 2:30 to 4:30 judges visit.

**Test run procedure:** a volunteer checks that `git status` is clean and `git log -1` matches the submitted hash. The unseen pack is released by link; run it with the one command. Three more messages arrive one at a time; run each as it arrives. Before one of them, write down which areas will make model calls and hand the slip over. Two of the three change the task; one is plausible but wrong, and you are not told which. Save the final plan and full trace to a file and upload it.

**Judge visit:** two judges visit separately, look at the saved plan, trace and interface, draw one team member by lot and ask two questions about the system (what each part is for and what would break without it). No slides.

**Scoring (100 points plus 10 bonus):**

| Component | Pts | What earns it |
|---|---|---|
| Output | 30 | Plan from the unseen pack passes six checks: correct figures, within budget, venue fits, schedule valid, enough judges, all areas covered |
| Catching the wrong message | 20 | Plan stays valid and the trace says why the message was rejected |
| Understanding | 20 | The drawn member explains each part and what breaks without it |
| Handling change | 10 | After each change the plan is valid again and only affected areas made model calls |
| UI | 10 | Interface shows plan, trace and rejected messages clearly and is easy to use |
| Predicting a change | 5 | Written prediction matches what the system did |
| Token use | 5 | Full run is among the leanest in the room and the plan passes every check |
| Bonus | 10 | Every model call uses a model on the organizers' small-model list (includes any model on your own laptop); plan must pass every check |

Tie-breaks in order: catching the wrong message, handling change, token use.

**Disqualification triggers:** a trace that misreports tokens, models or areas; facts or messages typed into code; code changed after 1:25. Agent count earns nothing, and a part you cannot justify costs points.

## 3. The sample pack (for understanding and test files only)

| # | From | Date | Message |
|---|---|---|---|
| 1 | Dean's office, email | 9 Nov | Approved: a 4-hour hackathon for 150 students in teams of 3. Budget is Rs 650,000, all in. Ten staff on duty. Keep a 15-minute prayer break. |
| 2 | Margalla Event Halls, email | 3 Nov | Room D seats 80 at Rs 40,000. Hall A seats 200 at Rs 120,000. Hall B seats 200 at Rs 150,000. Hall C seats 300 at Rs 220,000. Halls B and C have a standby generator. |
| 3 | Caterer, WhatsApp | 20 Oct | Standard lunch box Rs 1,000 per head. |
| 4 | Caterer, WhatsApp | 12 Nov | Salam bhai! Standard lunch box ab Rs 1,200 per head hoga, basic wala Rs 800. Delivery free hai. |
| 5 | Judging coordinator, email | 11 Nov | 20 judges confirmed. Honorarium Rs 5,000 each. A judge needs 15 minutes per team and should cover no more than three teams. |
| 6 | Finance, email | 10 Nov | Already ordered from the event budget: prizes Rs 100,000, backup internet Rs 20,000, printing Rs 10,000. |
| 7 | Student society, WhatsApp | 13 Nov | Can we get a DJ for the closing? The quote is Rs 50,000. |
| 8 | A judge, WhatsApp | 14 Nov | I may be 10 minutes late on the day. Traffic on Srinagar Highway. |

**Practice change:** "Finance here. The printing bill came in at Rs 15,000, not Rs 10,000."
**Practice wrong message:** "Caterer: I have rounded your order down to 100 boxes to keep the cost low." The event has 177 people to feed.

What the sample teaches: message 3 is out of date (superseded by 4). Message 4 mixes English and Roman Urdu and contains two options (standard, basic) and free delivery. Message 6 is money already spent. Message 7 is an unapproved request. Message 8 is irrelevant. The expected headcount is 177 = 150 students + 10 staff + 17 judges, where 17 = ceil(50 / 3) is the minimum number of judges needed, not the 20 confirmed.

## 4. Design decisions and why

| Decision | Reason |
|---|---|
| Exactly one model-backed component (the Extractor), one batched call per run | Fewer tokens scores higher; arithmetic by a model is unreliable |
| Everything else is deterministic Python | Guarantees correct figures and passes the six checks; explainable in one sentence per part |
| Generic key/constraint schema | Unseen constraint kinds must be handled without new code |
| Candidate-state validation before commit | A wrong message can never enter the plan; revert is free |
| Router in Python | Decides which areas recompute; zero tokens; makes the prediction slip deterministic |
| Local JSON state, no database | No network risk at 1:30; no setup; crash-safe |
| Local small model preferred | Bonus eligibility, no rate limits, works with bad Wi-Fi |
| Templates for explanations | An Explainer model call would cost tokens and add a part to defend |
| Static HTML report plus terminal output | No server to run; judges open one file |

## 5. Architecture and data flow

```
messages file
    |
    v
[1 Ingest]       split file into numbered raw message blocks
    |
    v
[2 Extractor]    ONE model call, tag "reading" -> JSON: message meta, facts, constraints
    |
    v
[3 Fact Store]   normalize, ground-check, resolve conflicts (latest date wins, protected facts)
    |
    v
[4 Router]       changed keys -> affected areas (pure Python)
    |
    v
[5 Planner]      run only affected solvers: venue, food, judging, schedule, budget
    |
    v
[6 Validator]    six checks + generic constraints + override floors on the CANDIDATE plan
    |
    +-- valid   -> commit state, write outputs
    +-- invalid -> discard candidate, keep previous plan, log rejection reason in trace
    |
    v
[7 Outputs]      terminal trace, out/final_plan.json, out/trace.txt, out/report.html
```

Fresh run: all five areas are solved. Update run: only the areas the Router returns are re-solved; other areas are copied from the previous plan.

## 6. Repository layout (every file and its purpose)

```
eventos/
  run.py                 entry point: argv -> session logic -> pipeline -> outputs
  config.json            model provider, model name, endpoint, timeouts, policy defaults
  requirements.txt       requests, pytest
  .gitignore             .eventos/ and out/ (so git status stays clean after runs)
  README.md              one paragraph: how to run, how to choose a model
  core/
    ingest.py            file -> list of message blocks
    llm.py               provider adapters (ollama, gemini, openai-compatible) -> LLMResult
    prompts.py           builds the extractor system and user prompts from templates
    extractor.py         calls llm, parses and schema-checks JSON, one retry
    factstore.py         stores facts, grounding check, conflict resolution, protected facts
    router.py            dependency table: changed keys -> affected areas
    constraints.py       generic constraint model and evaluator
    planner.py           orchestrates solvers in dependency order, builds candidate plan
    solvers/
      venue.py           choose hall
      food.py            choose option and quantity
      judging.py         required judges, assignment, honorarium
      schedule.py        build block timeline
      budget.py          sum costs, compare to cap, downgrade
    validator.py         the six checks plus constraints and floors
    trace.py             trace recorder and formatter, token totals
    state.py             load/save .eventos/state.json, session detection
    render.py            terminal output and HTML report
  tests/
    packs/               test message files (data, never code)
    fixtures/            saved extractor JSON for solver tests
    test_*.py            pytest files
  out/                   generated: final_plan.json, trace.txt, session_trace.txt, report.html
  .eventos/              generated: state.json
```

Every file must be small and single-purpose so any team member can explain it.

## 7. Configuration (`config.json`)

Configuration is not a pack fact. Policy defaults live here, never in code.

```
{
  "llm": {
    "provider": "ollama",
    "model": "<model name on the organizers' list>",
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

`provider` is one of `ollama`, `gemini`, `openai_compatible`. The model name written to the trace must come from the API response, not from this file (fall back to the config name only if the response omits it).

## 8. Canonical key vocabulary

The Extractor labels every fact with a key. Keys are the shared language between the model, the Fact Store, the Router and the solvers. The vocabulary below is schema, not data.

| Key | Meaning | Value type |
|---|---|---|
| event.students | number of students | number |
| event.team_size | students per team | number |
| event.teams | number of teams if stated directly | number |
| event.staff | staff on duty | number |
| event.duration_minutes | total event length in minutes (convert hours) | number |
| event.start_time | start clock time if stated | "HH:MM" |
| budget.cap | approved total budget | number |
| budget.committed.\<slug\> | money already ordered or spent on an item | number |
| budget.approved_extra.\<slug\> | extra spend explicitly approved | number |
| budget.request.\<slug\> | spend someone asks about, not approved | number |
| venue.option.\<slug\>.capacity | seats | number |
| venue.option.\<slug\>.price | hire cost | number |
| venue.option.\<slug\>.feature | a feature the option has (one fact per feature) | string |
| venue.choice | someone tries to set the chosen venue | slug string |
| food.option.\<slug\>.unit_price | price per person | number |
| food.option.\<slug\>.is_default | true if the sender calls it standard, regular or default | boolean |
| food.delivery_fee | delivery cost | number (0 if free) |
| food.quantity | someone tries to set the number of meals | number |
| judging.confirmed | judges confirmed | number |
| judging.rate | honorarium per judge | number |
| judging.minutes_per_team | minutes a judge needs per team | number |
| judging.max_teams_per_judge | most teams one judge may cover | number |
| judging.engaged | someone tries to set how many judges are used | number |
| custom.\<area\>.\<slug\> | anything else that matters | any |

Rules: slugs are lowercase snake_case; the same real-world item must use the same slug in every message; if a key does not fit, use `custom.<area>.<slug>` with the right area.

## 9. The Extractor

### 9.1 Purpose
Turn unstructured, multilingual text into structured facts and constraints. It does not plan, add, compare, convert currencies or decide.

### 9.2 Number of calls
One call per run for all new messages together, tag `reading`. In update mode the call contains only the new messages. A second call happens only as a retry after invalid JSON (also tag `reading`, also numbered in the trace).

### 9.3 System prompt (exact text template; fill placeholders in `prompts.py`)

```
You extract structured facts from event-planning messages. Reply with ONE JSON object only.
No prose, no markdown, no code fences. Do NOT plan, add, subtract, compare, or decide anything.
Copy numbers exactly as written. Messages can be English or Roman Urdu (Urdu in Latin letters).

For each message output an entry in "messages":
  id (the number given), sender, channel (email|whatsapp|notice|other), date (YYYY-MM-DD or null),
  relevance: "relevant" | "irrelevant" | "unapproved_request", reason (max 8 words).
  "irrelevant" = does not affect venue, schedule, food, judging or budget.
  "unapproved_request" = someone asks or suggests a spend or change that no approver accepted.

For useful information output "facts": {msg, key, value, unit, kind}.
  Use ONLY these keys when they fit: {{KEY_VOCABULARY}}
  Use custom.<area>.<slug> otherwise. Slugs are lowercase snake_case.
  Reuse the SAME slug for the same item in different messages.
  Convert hours to minutes for event.duration_minutes. Write "free" delivery as value 0.
  kind is one of: approval (an authority approves or fixes a value), quote (a price offer),
  commitment (money already ordered or spent), count, rate, capacity, duration,
  override (a sender tries to set a quantity or choice the plan would normally derive), request.
  Give each option its own fact lines. Never merge two options into one fact.
  If the same item is mentioned with two prices in different messages, output both.

For rules and limits output "constraints": {msg, area, type, target, op, value, unit, hard, text}.
  area: venue | schedule | food | judging | budget.
  type: schedule_block (a break or slot of fixed minutes; target = its name)
      | schedule_window (target "start" or "end", value "HH:MM")
      | require_feature (target = feature the venue must have)
      | forbid_item (target = something that must not be in the food)
      | metric_limit (target = a plan metric, op one of <=, >=, ==, value number)
      | other (describe in text)
  hard is true unless the sender says it is a preference.
  Plan metrics you may target: {{METRIC_VOCABULARY}}

{{KNOWN_KEYS_LINE}}
Output shape: {"messages":[...],"facts":[...],"constraints":[...]}
```

`{{KNOWN_KEYS_LINE}}` is empty in a fresh run. In update mode it is: `Existing keys (reuse the exact key when a fact updates one): [list]`. `{{METRIC_VOCABULARY}}` is the list of dotted metric names the validator exposes (section 16).

The user prompt is the raw message blocks, each prefixed with `MESSAGE <id>:`. No examples with real-looking facts may be added to the prompt; if few-shot examples are needed, use clearly synthetic placeholders.

### 9.4 Output schema (checked in Python)
- `messages[]`: id (int), sender (str), channel (str), date (str or null), relevance (enum), reason (str).
- `facts[]`: msg (int), key (str), value (number, string or boolean), unit (str or null), kind (enum).
- `constraints[]`: msg (int), area (enum of five), type (enum), target (str), op (str or null), value (any), unit (str or null), hard (bool), text (str).

### 9.5 Parsing and repair (`extractor.py`)
1. Strip code fences and leading text; locate the outermost JSON object.
2. `json.loads`. On failure do ONE retry call with the original input plus an appended line stating the output must be valid JSON only. Log it as the next numbered call.
3. Normalize numbers: remove thousands separators, strip currency words (Rs, PKR), convert `10k` style to thousands, convert English number words (one to twenty, thirty ... ninety, hundred, thousand) and strings of digits to numbers.
4. Drop facts with missing key or value; drop constraints with missing area or type; log each drop as a PYTHON line.
5. Lowercase and snake_case every key and slug.
6. **Grounding check (warning only):** for numeric facts, confirm the number appears in the source message after normalization. If not, mark the fact `grounded:false` and print a warning. Do not drop it (Roman Urdu number words cannot all be parsed).
7. If the second attempt also fails: raise `ExtractionFailed`; `run.py` prints the reason, keeps the previous plan, exits cleanly.

### 9.6 Failure cases and handling
| Failure | Handling |
|---|---|
| Invalid JSON | One retry, then keep previous plan |
| Model returns plan or arithmetic | Ignore unknown top-level keys; only messages, facts, constraints are read |
| Same item with different slugs | Fact Store fuzzy-merges (section 12) |
| Model marks a real fact irrelevant | Visible in trace; cannot be fully prevented; keep prompts clear |
| Model call timeout | Treated as extraction failure; plan unchanged; message recorded as unprocessed |

## 10. LLM client and trace (`llm.py`, `trace.py`)

`llm.call(system, user, tag)` returns `LLMResult(model, text, input_tokens, output_tokens, total_tokens, seconds)`.

- **Ollama:** POST `{base_url}/api/chat` with `model`, `messages`, `stream:false`, `format` set to the JSON schema (or `"json"`), `options.temperature=0`, `options.num_predict=max_output_tokens`. Read `message.content`, `model`, `prompt_eval_count`, `eval_count`. total = input + output.
- **Gemini:** POST `generateContent` with `responseMimeType: application/json`, `temperature: 0`. Read `usageMetadata.promptTokenCount`, `candidatesTokenCount`, `totalTokenCount` (use the reported total, which may include thinking tokens), and `modelVersion`.
- **OpenAI-compatible:** read `usage.prompt_tokens`, `completion_tokens`, `total_tokens`, and `model`.
- Timeout from config. A single `requests` session; no retries inside the adapter (retries are an extractor decision so they appear in the trace).
- Token numbers are never computed locally. If the API gives none, print `tokens: not reported` and add 0 to the total, never an estimate.

**Trace recorder.** `Trace.record_model_call(n, model, tag, input, output, tokens)` and `Trace.python_event(kind, text)`. Trace formatting:

```
=== RUN 1 (fresh) | file: pack.txt | 8 messages ===
MODEL CALL 1
  model: <model name from response>
  area: reading
  input: <full system prompt + user prompt>
  output: <full raw model output>
  tokens: input=<n> output=<n> total=<n>
PYTHON | EXTRACT   | 14 facts, 3 constraints, 1 irrelevant, 1 unapproved_request
PYTHON | RESOLVE   | food.option.standard_lunch_box.unit_price: 1000 (20 Oct) -> 1200 (12 Nov), later date wins
PYTHON | ROUTER    | affected areas: venue, food, judging, schedule, budget
PYTHON | SOLVE     | venue -> Hall A (capacity 200 >= 177, cheapest fitting)
PYTHON | VALIDATE  | 6/6 checks passed
PYTHON | COMMIT    | plan v1 saved
TOTAL TOKENS: <sum of this run's model calls>
```

Rules: model-call blocks are numbered from 1 in each run; PYTHON lines are never numbered and never carry an area tag (so they cannot be mistaken for model calls); the tag on a model call is always `reading` in this design; the last line of every run is `TOTAL TOKENS: n`. `out/session_trace.txt` appends each run's block in order and ends with `SESSION TOTAL TOKENS: n`. Upload `session_trace.txt` and `final_plan.json` at the end.

## 11. Ingest (`ingest.py`)

Goal: split the file into message blocks without guessing meaning. Do not extract sender or date here; the Extractor does that.

Algorithm (in order, first that yields 2 or more blocks wins):
1. Lines that start with an index such as `1.`, `1)`, `#1`, `Message 1:`, or a markdown table row beginning with `|` and a number.
2. Blocks separated by one or more blank lines.
3. Each non-empty line is a message.
Each block becomes `{id: sequential int starting at 1 for the file, text: raw block, hash: sha1(normalized text)}`. Normalization for hashing: lowercase, collapse whitespace. A file with one message yields one block. Empty file: print "no messages found", exit 0, change nothing.

## 12. State and session logic (`state.py`)

`.eventos/state.json` holds:

```
{
  "version": 3,
  "messages": [ {"seq":1,"hash":"..","text":"..","meta":{sender,channel,date,relevance,reason},
                 "status":"applied|rejected|ignored"} ],
  "facts": [ {..fact fields.., "seq":1, "date":"2026-11-09", "superseded_by": null} ],
  "constraints": [ ... ],
  "plan": { ... last VALID plan ... },
  "rejections": [ {"seq":9,"sender":"..","text":"..","check":"food_quantity","reason":".."} ],
  "runs": 2
}
```

**Session detection (`run.py`):**
- No state file: fresh run.
- State exists and at least one input block hash is already in state: update mode; only blocks with unseen hashes are sent to the Extractor. Nothing new: print "no new messages", re-print the existing plan, exit.
- State exists, no hash overlap, and the input has 2 or fewer blocks: update mode (a single new message file).
- State exists, no hash overlap, and the input has 3 or more blocks: new pack; archive old state to `.eventos/archive/<timestamp>.json` and run fresh.
Before the official test run delete `.eventos/` or use a fresh clone (it is git-ignored, so `git status` stays clean either way).

Sequence numbers: each message gets a global `seq` in arrival order across runs.

## 13. Fact Store (`factstore.py`)

### 13.1 Date assignment
Parse the model's date with the system clock year when the year is missing. If a message has no date: in a fresh pack it inherits the date of the previous message; in update mode it gets the latest date already in the store. Ties break by `seq`.

### 13.2 Conflict resolution (latest wins)
Two facts conflict when they have the same normalized key (after fuzzy matching, 13.3). The fact with the later `(date, seq)` wins; the loser is marked `superseded_by` and a PYTHON `RESOLVE` line is printed with old value, new value and the reason. Multi-valued keys (`...feature`) never conflict; they accumulate.

### 13.3 Fuzzy key matching
When a new key is not in the store, compare it to existing keys with the same prefix (`area.type`) using `difflib.SequenceMatcher` on the slug. If ratio is at least 0.8, treat it as the same key and log the merge. This protects against the model writing `standard_lunch` and `standard_lunch_box`.

### 13.4 Protected facts
When `policy.protect_approved_facts` is true, facts with `kind=approval` on these keys are protected: `event.students`, `event.duration_minutes`, `budget.cap`, `event.staff`, `event.team_size`. A later message that changes a protected key is accepted only if its sender matches the original approver (SequenceMatcher ratio of lowercased senders at least `sender_match_threshold`). Otherwise the whole message is rejected with reason `unauthorized change to approved value <key>: approved by <sender>`. This catches plausible but wrong messages that no arithmetic invariant would catch.

### 13.5 Relevance handling
- `irrelevant`: stored as message only; no facts applied; trace line `IGNORED message <seq>: <reason>`.
- `unapproved_request`: facts stored under `budget.request.*`; never added to costs when `exclude_unapproved_requests` is true; listed in the plan under `excluded_requests` with the reason `no approval stated`.
- `relevant`: facts applied.

### 13.6 Changed keys
Every `apply()` call returns the set of keys whose winning value changed. This set is the Router's input.

## 14. Router (`router.py`)

A static dependency table maps key patterns to the areas that depend on them. This is a relationship table, not data.

| Key pattern | Areas to re-solve |
|---|---|
| event.students, event.team_size, event.teams | venue, food, judging, schedule, budget |
| event.staff | venue, food, budget |
| event.duration_minutes, event.start_time | schedule |
| budget.cap | budget |
| budget.committed.*, budget.approved_extra.*, budget.request.* | budget |
| venue.option.*, venue.choice | venue, budget |
| food.option.*, food.delivery_fee, food.quantity | food, budget |
| judging.confirmed, judging.engaged | judging, venue, food, schedule, budget |
| judging.rate | judging, budget |
| judging.minutes_per_team, judging.max_teams_per_judge | judging, schedule, venue, food, budget |
| custom.\<area\>.* and constraints of area X | area X, budget |

Judging changes can alter headcount (engaged judges), so they cascade to venue, food and budget.

**Output:** an ordered list following the planning order `judging, venue, food, schedule, budget`, never containing duplicates. Fresh runs return all five. The Router also emits `model_call_areas`: the list of tags that will call a model, which in this design is always `["reading"]`. This is what the prediction slip is written from.

## 15. Planner and solvers

`planner.build(facts, constraints, previous_plan, areas)` returns a candidate plan. Areas not in `areas` are copied from `previous_plan`. Solvers run in this order because each uses the previous one: judging, venue, food, schedule, budget. All solvers are pure functions over the current winning facts; each returns `{result, line_items, warnings}`.

### 15.1 Derived quantities (`planner.py`)
- `students = event.students`
- `teams = event.teams` if stated, else `ceil(students / event.team_size)`
- `staff = event.staff` (0 if absent, with a warning)
- `judges_engaged` from judging solver
- `headcount = students + staff + judges_engaged`
If an input is missing, the solver returns `status: "missing"` listing the missing keys; the validator reports it under "all areas covered".

### 15.2 Judging (`solvers/judging.py`)
Inputs: teams, judging.max_teams_per_judge (M), judging.minutes_per_team (T), judging.confirmed (C), judging.rate (R), optional judging.engaged override.
1. `required = ceil(teams / M)`.
2. If policy is `minimum_required`: `engaged = required`; if policy is `all_confirmed`: `engaged = C`. An `engaged` override replaces this and is subject to the floor check.
3. If `C < required`: status `insufficient`, `shortfall = required - C` (validator will flag).
4. Assign teams to judges round-robin: team `i` goes to judge `i mod engaged`. Max teams per judge actual `k = ceil(teams / engaged)` (must be at most M).
5. `judging_window_minutes = k * T`.
6. `honorarium_total = engaged * R`.
Output: required, engaged, confirmed, per_judge assignment, window, honorarium_total.

### 15.3 Venue (`solvers/venue.py`)
Inputs: headcount, venue options with capacity, price, features; required features from `require_feature` constraints; optional `venue.choice` override.
1. Candidates = options where `capacity >= headcount` and all required features are present.
2. Pick the lowest price; ties break by smaller capacity, then slug order.
3. If an override names a slug, use it; the validator will check fit.
4. If no candidate: status `no_fit`, list rejected options with reasons (`capacity 80 < 177`, `missing feature generator`).
Output: chosen slug and details, price, a list of rejected options with reasons, and the slack seats (`capacity - headcount`).

### 15.4 Food (`solvers/food.py`)
Inputs: headcount, food options (latest unit prices), `is_default` flag, delivery fee, `forbid_item` constraints, optional `food.quantity` override.
1. `quantity = headcount` (override replaces; floor check in validator).
2. Option order: the default option first; then others by descending price (nicer first) if `food_preference` is `default_then_cheapest`, the fallback chain used by the budget solver goes by ascending price.
3. `food_cost = quantity * unit_price + delivery_fee` (delivery is 0 if not stated).
4. If a `forbid_item` constraint names an option or a word in its slug, that option is excluded.
Output: option, unit price, quantity, delivery fee, cost.

### 15.5 Schedule (`solvers/schedule.py`)
Inputs: `event.duration_minutes` (D), `event.start_time` (optional), schedule_block constraints, judging window, policy opening and closing minutes, `build_split_before_breaks`.
1. Blocks to place: Opening (O), Judging (window W), Closing (Cl), and every `schedule_block` constraint (name, minutes).
2. `build_total = D - O - sum(breaks) - W - Cl`. If negative: status `overflow` with the shortfall.
3. `build1 = floor(build_total * split)`; `build2 = build_total - build1`.
4. Order: Opening, Build 1, each required break in the order given, Build 2, Judging, Closing. Honor `schedule_window` constraints by shifting the start or flagging a conflict if the window is smaller than D.
5. Compute offsets from zero, and clock times if `event.start_time` exists.
6. Late arrivals and similar notes without a constraint do not change the schedule.
Output: ordered blocks `{name, start_offset, end_offset, minutes, clock_start, clock_end}`, with `sum(minutes) == D` guaranteed.

### 15.6 Budget (`solvers/budget.py`)
Inputs: venue price, food cost, honorarium_total, sum of `budget.committed.*`, sum of `budget.approved_extra.*`, `budget.cap`.
1. `total = venue + food + honorarium + committed + approved_extras`.
2. If `total <= cap`: done.
3. Else downgrade in this fixed order, recomputing after each step: (a) cheaper food option; (b) cheaper venue that still fits; (c) stop. Each step is logged as a PYTHON `DOWNGRADE` line.
4. If still over: status `over_budget` with `overage`.
Output: line items list, total, cap, remaining, status.
Excluded requests are not part of `total`.

## 16. Constraints (`constraints.py`)

### 16.1 Types and how each is enforced
| Type | Where used | Enforcement |
|---|---|---|
| schedule_block | schedule solver | Block is inserted; validator checks present and minutes at least the stated value |
| schedule_window | schedule solver | Start or end clock time must match; validator checks |
| require_feature | venue solver | Filters venue candidates; validator checks chosen venue has it |
| forbid_item | food solver | Excludes options; validator checks |
| metric_limit | validator | Compares a plan metric to the value with the operator |
| other | none | Reported as `unevaluated` in the trace and plan warnings; never silently ignored |

### 16.2 Metric vocabulary
The validator exposes a flat dictionary of the plan, used by `metric_limit`:
`event.headcount`, `event.students`, `event.staff`, `event.teams`, `venue.capacity`, `venue.price`, `venue.slack`, `food.quantity`, `food.unit_price`, `food.cost`, `judging.engaged`, `judging.required`, `judging.window_minutes`, `judging.honorarium_total`, `schedule.total_minutes`, `schedule.break_minutes`, `budget.total`, `budget.cap`, `budget.remaining`.
A `metric_limit` whose target is not in this list is reported as `unevaluated`.

### 16.3 Examples of unseen constraints the system must cover without code changes
- "Lunch must be vegetarian friendly" -> forbid_item or `other` (reported).
- "Venue needs a prayer room / generator / projector" -> require_feature.
- "No more than Rs 200,000 on food" -> metric_limit `food.cost <= 200000`.
- "Event must end by 17:00" -> schedule_window.
- "Add a 30-minute networking session" -> schedule_block.
- "Judges must get lunch" is already covered by headcount.

## 17. Validator (`validator.py`)

Runs on the candidate plan; returns `{passed: bool, checks: [...], failures: [...]}`. Each failure has a `check` id and a templated human reason. The six official checks are recomputed independently from raw facts; they must not simply trust solver outputs.

| # | Check id | Passes when |
|---|---|---|
| 1 | figures | headcount equals students + staff + engaged; teams equals the stated or ceil value; food cost equals quantity times unit price plus delivery; honorarium equals engaged times rate; budget total equals the sum of its line items |
| 2 | budget | `total <= cap` |
| 3 | venue_fit | chosen capacity at least headcount and every required feature present |
| 4 | schedule | block minutes sum to duration; every required block present with at least the stated minutes; judging window equals the expected value; no overlaps; window and start constraints respected |
| 5 | judges | `engaged >= required` and `engaged <= confirmed` and per-judge teams at most the limit |
| 6 | coverage | all five areas present and none have status missing, insufficient, no_fit, overflow or over_budget |
| 7 | constraints | every `metric_limit`, `require_feature`, `forbid_item`, `schedule_block`, `schedule_window` passes; `other` ones are listed as unevaluated warnings (not failures) |
| 8 | floors | every override respects its floor: food.quantity at least headcount, judging.engaged at least required, venue.choice has capacity at least headcount |

Failure message templates:
- food: `Rejected: food quantity <n> is below the <h> people to feed`
- budget: `Rejected: total Rs <t> exceeds the approved cap of Rs <c> by Rs <o>`
- venue: `Rejected: <venue> seats <cap>, below headcount <h>`
- judges: `Rejected: <n> judges engaged, <r> needed at <m> teams each`
- protected: `Rejected: <key> was approved by <sender>; <other sender> cannot change it`
Templates take their numbers from the computed plan, never from the model.

## 18. Update flow, rejection and commit (`run.py` + `planner.py`)

```
state = load_state()                         # may be None
blocks = ingest(file)
mode = detect_session(state, blocks)         # fresh | update | nothing_new
new_blocks = blocks not already in state
result = extractor.run(new_blocks, known_keys=state.keys if update else [])   # 1 model call
for each new message (in seq order):
    candidate_facts = copy(state.facts); candidate_constraints = copy(state.constraints)
    changed = factstore.apply(message, candidate_facts)      # may raise Protected/Unapproved
    areas = router.affected(changed)                          # fresh: all five
    candidate_plan = planner.build(candidate_facts, candidate_constraints, state.plan, areas)
    verdict = validator.check(candidate_plan, candidate_facts, candidate_constraints)
    if verdict.passed or mode == fresh and message is part of initial pack:
        commit(candidate_*)                       # state advances
    else:
        discard candidate; record rejection; PYTHON REJECT line; state.plan unchanged
write state, plan, trace, report; print plan summary and TOTAL TOKENS
```

Notes:
- **Fresh run:** apply all messages together, solve once, validate once. If the result is invalid (for example true shortfall of judges), still output the plan with `valid:false` and the failing checks visible; nothing is rejected because there is no earlier plan to protect.
- **Update run:** messages are processed one at a time in order. Each is tested against the plan produced by the previous accepted message. A message is accepted or rejected as a whole (all of its facts).
- **Reasons are templated:** the `REJECT` line includes message seq, sender, check id and numbers: `PYTHON | REJECT | message 9 (Caterer): food quantity 100 is below the 177 people to feed. Plan unchanged.`
- **No extra model call is used for rejection.** The reason is assembled by the validator.
- **Zero-impact updates** (irrelevant messages) skip the Router, solvers and validator and leave the plan unchanged.
- The prediction slip is derived from the router: it lists `reading` as the only area that calls a model, and the affected solver areas as Python-only.

## 19. Outputs

### 19.1 `out/final_plan.json`
```
{
  "valid": true,
  "version": 2,
  "headcount": {"students": n, "staff": n, "judges": n, "total": n},
  "venue": {"name": "..", "capacity": n, "price": n, "slack": n, "rejected_options": [...]},
  "schedule": {"duration_minutes": n, "blocks": [{"name","start","end","minutes"}]},
  "food": {"option": "..", "unit_price": n, "quantity": n, "delivery_fee": n, "cost": n},
  "judging": {"teams": n, "required": n, "confirmed": n, "engaged": n,
              "assignments": [{"judge": 1, "teams": [..]}], "window_minutes": n, "honorarium_total": n},
  "budget": {"cap": n, "total": n, "remaining": n,
             "items": [{"label","amount","source_message"}]},
  "excluded_requests": [{"item","amount","reason"}],
  "rejections": [{"seq","sender","check","reason"}],
  "warnings": [".."],
  "checks": [{"id","passed","detail"}],
  "recomputed_areas": ["budget"],
  "tokens": {"last_run": n, "session": n}
}
```

### 19.2 Terminal output order
1. Trace (as in section 10).
2. Plan summary: five labelled sections with key figures.
3. Checks table (six official checks with pass or fail).
4. Rejected or excluded messages with reasons.
5. Final `TOTAL TOKENS` line (last line of the run).

### 19.3 `out/report.html` (the UI)
Self-contained static file (inline CSS, no external requests, no JavaScript required). Regenerated every run. Layout, top to bottom:
1. Header: event title, validity badge (green valid / red invalid), version, last run mode (fresh or update), tokens (run and session).
2. **Plan cards** (five): venue, schedule (timeline bar), food, judging (assignment summary), budget (line items table with a cap meter).
3. **Checks panel:** the six official checks with green or red marks.
4. **Rejected and excluded messages panel:** red cards with sender, message text, failed check, reason; amber cards for excluded requests and ignored messages.
5. **Trace panel:** collapsible blocks per model call (model, tag, tokens, input, output), PYTHON events listed, total tokens.
6. **Change panel:** which areas recomputed in the last update and which were reused, plus the router decision.
Readable at a glance in under 10 seconds; no navigation needed.

## 20. Worked example (sample pack, to verify your implementation)

Extracted winning facts: students 150, team size 3, staff 10, duration 240 min, cap 650,000, prayer block 15 min; venue options and prices as listed; standard box 1,200 (12 Nov overrides 1,000), basic 800, delivery 0; judges confirmed 20, rate 5,000, 15 min per team, at most 3 teams; committed 100,000 + 20,000 + 10,000; DJ request 50,000 (unapproved); late judge irrelevant.

Computation:
- teams = ceil(150 / 3) = 50.
- required judges = ceil(50 / 3) = 17; engaged = 17; headcount = 150 + 10 + 17 = 177.
- Venue: capacity at least 177 gives Hall A (200), Hall B (200), Hall C (300); cheapest is Hall A at 120,000. Room D (80) rejected: capacity 80 < 177.
- Judging: per judge k = ceil(50 / 17) = 3 teams; window = 3 x 15 = 45 min; honorarium = 17 x 5,000 = 85,000.
- Food: standard at 1,200 x 177 = 212,400; delivery 0.
- Committed: 130,000.
- **Total = 120,000 + 212,400 + 85,000 + 130,000 = 547,400**; cap 650,000; remaining 102,600.
- Schedule (policy opening 15, closing 15, split 0.5): build total = 240 - 15 - 15 - 45 - 15 = 150; build 1 = 75; build 2 = 75. Blocks: Opening 0-15, Build 75, Prayer 15, Build 75, Judging 45, Closing 15 = 240.
- DJ: excluded, `no approval stated`. Late judge: ignored as irrelevant.

Update 1 (change): printing 10,000 becomes 15,000. Router: `budget.committed.printing` changed, so only budget is re-solved. New committed total 135,000; total = **552,400**; valid. Model calls: 1 (`reading`).

Update 2 (wrong): caterer states 100 boxes. Extractor emits override `food.quantity = 100`. Candidate food quantity 100 < headcount 177; floors check fails; message rejected; plan stays at total 552,400; trace prints the reason.

If the policy were `all_confirmed` (20 judges): headcount 180, food 216,000, honorarium 100,000, total 566,000 (also valid). Keep the policy in `config.json` and confirm with the help desk.

## 21. Edge cases and required behavior

| Case | Behavior |
|---|---|
| Two quotes, different dates | Later date wins; logged |
| Quote without a date | Takes the previous message's date (fresh) or the latest date (update) |
| Roman Urdu price phrase | Extractor reads it; grounding check warns if number not found |
| Free delivery | delivery fee 0 |
| Prices in lakh or k | Normalized to numbers in extractor.py |
| Hours given for duration | Converted to minutes by the model per prompt and re-checked as numeric |
| Hall options but no capacity fact | Option incomplete: excluded with reason `missing capacity` |
| Judges confirmed below required | `judges` check fails; plan flagged invalid with shortfall; not silently adjusted |
| Message changes student count | Router cascades to all areas; protected-fact rule applies |
| Message adds a new constraint type | Evaluated by generic types, else reported as unevaluated |
| New constraint makes the plan invalid | Rejected at update; plan unchanged; reason printed |
| Cap lowered below committed spend | Rejected: `total exceeds cap`; plan unchanged |
| Same message file run twice | `nothing_new`: re-print existing plan, 0 model calls |
| Model returns garbage twice | Extraction failure line; plan unchanged; exit 0 |
| Empty or one-line file | Clear message; no crash |
| Model slow | Timeout from config; failure path above |

## 22. Testing

Tests live in `tests/`; message packs and expected values are data files, never embedded in code.

1. **Solver unit tests** (pytest, using `tests/fixtures/*.json` fact sets with invented numbers): venue picks cheapest fitting; features filter; judging ceil and round-robin; budget downgrade chain; schedule sums to duration; negative build overflow.
2. **Validator tests:** each of the eight checks failing on a hand-broken plan.
3. **Fact Store tests:** later date wins; undated fallback; fuzzy slug merge; protected fact rejection.
4. **Router tests:** each table row returns the expected areas, in planning order.
5. **Extractor tests:** repair of fenced JSON, number normalization, retry path (with a stub LLM).
6. **End-to-end on the sample pack** against section 20 values (with the real model): all six checks pass, total 547,400, trace well formed.
7. **Practice change and wrong message** as updates: totals and rejection reason as in section 20.
8. **Unseen-style packs** you write yourself: different numbers and senders, Roman Urdu phrasing, and at least three new constraint kinds (a required feature, a cap on one cost line, a schedule window, an extra schedule block).
9. **Audit:** `grep -nE "[0-9]{3,}" core/ run.py` must show no pack values; no sample hall names, senders or message sentences in code.
10. **Timing:** a full run under 120 s and an update under 60 s on the target laptop with the chosen model; measure and record.
11. **Clean clone test:** clone, install, delete `.eventos/`, run the sample, run both updates, confirm `git status` is clean afterwards.

## 23. Build order (10:00 to 1:25) and ownership

| Time | Deliverable | Owner |
|---|---|---|
| 10:00-10:20 | Repo, `.gitignore`, config, model access test (on the list, speed, JSON quality), first push | All |
| 10:20-11:00 | `ingest`, `llm`, `prompts`, `extractor`, `trace`, minimal `run.py` printing a real trace | A |
| 10:20-11:00 | Five solvers and `planner` against fixture facts | B |
| 10:20-11:00 | `factstore`, `router`, `state` | C |
| 11:00-11:30 | Merge: end-to-end fresh run on sample pack | All |
| 11:30-12:00 | `validator`, `constraints`, rejection flow, update mode | B and C |
| 12:00-12:30 | Tests, unseen-style packs, token tuning, prompt fixes | A and C |
| 12:30-1:00 | `render.py`: terminal summary, `report.html` | C |
| 1:00-1:15 | Rehearsal: fresh clone, sample, two updates, slip, interview drill, audit | All |
| 1:15-1:25 | Final commit, push, submit repo link and commit hash. Stop. | All |

Merge points at 11:00, 12:00, 1:00. Nothing risky after 1:15. No edits after 1:25.

## 24. Prediction slip and judge Q&A

**Prediction slip.** Before one of the three messages, write: `Model calls will be: reading (1 call). Python-only recompute: <areas the router returns>.` Determine the router output by reading the message and mapping it with the table in section 14 (a cost change gives budget; a change to students gives all five areas; a food price or quantity gives food and budget). Confirm the slip meaning at the help desk (section 25).

**Each member must answer, for every part, what it does and what breaks without it:**

| Part | What it does | If removed |
|---|---|---|
| Ingest | Splits any text file into messages | The one command cannot read an unseen file |
| Extractor | Reads English and Roman Urdu into structured facts | No understanding of unseen messages |
| Fact Store | Keeps the latest valid value, protects approved values | Stale quotes win, unauthorized changes slip in |
| Router | Finds affected areas | Everything recomputes; change handling and slip fail |
| Solvers | Do exact arithmetic and selection | Wrong figures, more tokens |
| Validator | Checks the six rules on a candidate | A wrong message such as 100 boxes enters the plan |
| State file | Remembers the plan between runs | Updates cannot build on the previous plan |
| Trace | Records every model call truthfully | Disqualification; no reasons shown |
| Report | Shows plan, trace, rejections | UI score lost |

**Likely questions and short answers:**
- Why one model call? Reading is the only language task, so tokens are minimal and the run is fast.
- Why not let the model do the math? It can be wrong; code is exact and free.
- How do you catch the wrong message? The candidate plan fails a validator check, so the message is discarded and the reason printed.
- What if the venue Wi-Fi fails? A local model and local files need no network.
- How does an unseen constraint work? It arrives as a typed constraint and a generic evaluator checks it; unknown kinds are reported, not ignored.
- Why 17 judges and not 20? 17 is the minimum for 50 teams at 3 teams each; the policy can be changed in config.

## 25. Open questions (ask at the help desk) and defaults used until answered

| Question | Default |
|---|---|
| Judges used for cost and food: minimum required or all confirmed? | minimum required (matches 177) |
| How are update messages delivered (new file only, or pack plus new)? | Both supported (section 12) |
| Does the prediction slip name the model tag or the affected area? | Write both: `reading` for model calls, router areas as Python-only |
| Which models are on the small-model list? | Pick from the list; verify before 10:30 |
| Unapproved requests such as the DJ: exclude or include if budget allows? | Exclude and list with reason |
| Are opening and closing slots expected in the schedule? | Included via config policy (15 minutes each) |

## 26. Final checklists

**Before code freeze (1:25):**
- [ ] `python run.py <file>` works with no arguments beyond the path, from a fresh clone
- [ ] Trace shows numbered calls with real model name, tag `reading`, input, output, real token counts, total tokens
- [ ] No pack facts, names, dates or message text in code (audit passed)
- [ ] Sample pack gives total 547,400 and six checks pass
- [ ] Change message recomputes only budget; wrong message is rejected with a printed reason
- [ ] Full run under 2 minutes, update under 1 minute, at most 5 model calls per update
- [ ] `out/` and `.eventos/` are git-ignored; `git status` clean; commit hash recorded
- [ ] Local model works with Wi-Fi off; fallback provider tested
- [ ] Every member can answer the section 24 table without notes

**During the test run (1:30):**
- [ ] Start from a clean clone or delete `.eventos/`
- [ ] Run the unseen pack; note time and tokens
- [ ] Write the prediction slip before the chosen message
- [ ] Run each of the three messages as it arrives
- [ ] Save `out/final_plan.json` and `out/session_trace.txt` and upload them
- [ ] Keep `out/report.html` open for the judges

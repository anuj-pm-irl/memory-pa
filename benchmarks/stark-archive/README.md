# The Stark Archive

> Sir, the elevator has a rehearsal schedule, the basil has representation, and I have filed your orange juice under logistics. The June archive is ready.
>
> JARVIS

Tony Stark's alternate-universe archive follows one month at the tower after a neighborhood blackout. It contains 18 fictional source notes, six topics, and 17 linked people and projects. The scale target was one tenth of a 175-note reference archive by note count. The Stark notes contain 18.3 KiB of source text.

Run `memory-pa demo` to explore the archive and preview a reminder backed by the field kitchen note. [Browse the generated workspace](../../examples/workspace/index.md)

## Read the logs

| Topic | June 2032 records |
| --- | --- |
| Tower access | [The elevator learns to whisper](notes/tower-access/elevator-learns-to-whisper.md), [The cello complaint](notes/tower-access/cello-complaint.md), [The elevator keeps its voice](notes/tower-access/elevator-keeps-its-voice.md), [The night badge gets its own desk](notes/tower-access/badge-gets-its-own-desk.md) |
| Harbor Clinic | [The hologram that needs a human](notes/harbor-clinic/hologram-needs-a-human.md), [A short life for a long queue](notes/harbor-clinic/short-life-for-long-queue.md), [The tablet forgets first](notes/harbor-clinic/tablet-forgets-first.md) |
| City Lanterns | [After the lights go out](notes/city-lanterns/after-the-lights-go-out.md), [A lamp for the bus stop](notes/city-lanterns/lamp-for-bus-stop.md), [The rain rule](notes/city-lanterns/rain-rule.md) |
| Workshop | [DUM-E gets a report card](notes/workshop/dum-e-report-card.md), [Captain America borrows a dolly](notes/workshop/captain-borrows-a-dolly.md), [The robot earns Saturday](notes/workshop/robot-earns-saturday.md) |
| Field kitchen | [Breakfast in a blackout](notes/field-kitchen/breakfast-in-a-blackout.md), [The card in the red sleeve](notes/field-kitchen/card-in-red-sleeve.md), [We bought too much orange juice](notes/field-kitchen/too-much-orange-juice.md) |
| Roof garden | [The birds request a change order](notes/roof-garden/birds-request-a-change-order.md), [When the basil gets a lawyer](notes/roof-garden/basil-gets-a-lawyer.md) |

James Rhodes appears in both lift and watering records. The switchplate assignment and its completion share an action ID. Two crews put different paperwork in a red sleeve. [Capture metadata](corpus.json) · [Gold queries and their evidence](gold.json)

## Benchmark results

Local run on an Apple M5 Pro with macOS 26.6, Python 3.12.14, and memory-pa 0.1.3. The validated workspace opened all 18 source texts byte for byte and verified all 42 annotated evidence quotes.

| Answerable queries | Hit@1 | Hit@5 | Hit@10 |
| --- | ---: | ---: | ---: |
| Direct lookup | 11/12 | 12/12 | 12/12 |
| Timeline and status | 6/8 | 8/8 | 8/8 |
| Paraphrase | 1/6 | 1/6 | 1/6 |
| Alias | 1/4 | 2/4 | 2/4 |
| Multiple notes | 5/6 | 6/6 | 6/6 |
| **Overall** | **24/36 (66.7%)** | **29/36 (80.6%)** | **29/36 (80.6%)** |

Mean recall of the annotated notes was **79.2% at five** and **80.6% at ten**. MRR@10 was **0.725**. Five of six multi-note queries surfaced every required note in the first five hits. All six did by ten. Four of six unanswerable queries returned an empty result.

| Operation | Samples | p50 | p95 |
| --- | ---: | ---: | ---: |
| Fresh CLI search | 210 | 64.6 ms | 71.5 ms |
| Search with workspace already loaded | 1,680 | 0.204 ms | 0.226 ms |
| CLI open original source text | 18 | 63.6 ms | 66.5 ms |
| CLI capture preview and apply | 18 | 136.3 ms | 150.1 ms |

- `quiet window` puts four sections of the roof record ahead of the lift decision. The lift decision appears at rank seven.
- `rhodey final lift hours` finds the switchplate installation. The approval uses `James Rhodes` and gives the hours as 21:30 to 23:00.
- `approved fourteen-day` finds the clinic's final decision because those words both occur in the source text. The decision gives the check-in text twenty-four hours and drops the fourteen-day option.

The full results include the dataset hash, per-query ranks, returned sections, and timing summaries. [Results JSON](results.json)

## Run it

From the repository root, use Python 3.11 or newer.

```sh
python -m pip install -e .
python benchmarks/stark-archive/benchmark.py > stark-results.json
```

The runner uses `memory-pa add` preview and apply in a temporary local store. It validates the snapshot, opens each original source with `show`, and checks every gold quote. Each gold case gives the reader's question, the literal `search` input, and the notes that support it. Every input runs with `--limit 10`. Each CLI timing includes a fresh Python process, the local store read, validation, and JSON output. The loaded-workspace timings measure `Workspace.search` against the same snapshot and query mix. Runs shuffle cases with a fixed seed.

Hit@K means at least one gold note appears among the first K returned sections. A note that matches in several sections uses several result slots and counts once toward recall. MRR@10 averages the reciprocal rank of the first gold hit, with zero for a miss. Unanswerable cases check for an empty result when the archive contains no evidence that supports the question's premise. The benchmark covers local note retrieval on this dataset.

To explore the captured archive in a shell, export the workspace and open it in a disposable store.

```sh
STARK_TMP=$(mktemp -d)
python benchmarks/stark-archive/benchmark.py --cli-repeats 1 --warm-repeats 1 \
  --export "$STARK_TMP/archive" > "$STARK_TMP/results.json"
memory-pa --store "$STARK_TMP/workspace" init --from "$STARK_TMP/archive"
memory-pa --store "$STARK_TMP/workspace" search "purple tags"
memory-pa --store "$STARK_TMP/workspace" show \
  topics/field-kitchen/the-card-in-the-red-sleeve-2032-06-20.md --section source-text
```

# Recall benchmarks

## LongMemEval-S with Codex

Each of the 500 questions ran in a fresh, read-only Codex session with a local memory-pa workspace. One note per conversation session held its dated messages. The agent used `memory-pa search` to try and refine keywords and `memory-pa show` to open original source text. Citation scoring counted an expected source only when the tool trace showed that the agent had opened it. A separate model call graded each answer against the dataset reference. [LongMemEval project](https://github.com/xiaowu0162/LongMemEval) · [Cleaned dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)

| Measure | Result |
| --- | ---: |
| Correct answers, including abstentions | 442/500 (88.4%) |
| Answerable questions with at least one expected source cited | 466/470 (99.1%) |
| Answerable questions with every expected source cited | 369/470 (78.5%) |
| Correct abstentions | 27/30 (90.0%) |

This run used memory-pa 0.1.3 and GPT-6.2 Sol at low reasoning effort for both the agent and the separate grading call. The median question took four search commands and 19.0 seconds. The cleaned dataset had SHA-256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.

## Stark Archive local search

This run passed each benchmark query directly to the CLI's local keyword search. At least one expected note appeared in the top five results for 29 of 36 answerable queries (80.6%). The 18-note fictional archive includes dated decisions, tasks that change status, and people who appear in more than one topic. [Queries, scoring, and results](../benchmarks/stark-archive/README.md#benchmark-results)

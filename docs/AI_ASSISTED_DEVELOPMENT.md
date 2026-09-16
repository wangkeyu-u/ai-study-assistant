# AI-assisted development

Codex assisted the September 2026 retrieval changes: component switches, a reproducible ablation runner, regression tests and documentation. Earlier Qoder attribution remains in Git history.

## Evidence from this revision

- The challenge set retains 48 original queries and adds 63 AI-authored synthetic cases. These are not independent human labels.
- Eight retrieval variants ran against the same frozen corpus, with three repetitions per variant. Inputs, model revisions, code hashes and per-query output are in the [experiment record](experiments/retrieval-ablation.md).
- Tests and type checks cover the implementation. The [failure log](failures/001-small-benchmark.md) records the old small-corpus limitations and metric mismatch.

The experiment supports inspection of component trade-offs; it does not establish general RAG accuracy. The developer remains responsible for accepting the data labels, retrieval policy and deployment scope. No model parameters were fine-tuned in this revision.

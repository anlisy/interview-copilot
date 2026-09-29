# Stage6 Dataset Human Review Checklist

Before using the formal dataset as final Ground Truth, review every case for:

1. **Intent correctness**
   - `expected` really matches the underlying task intent.
   - Intent cases compare two questions, not just one question.
2. **Ambiguity**
   - There is a defensible single expected choice.
   - Distractor options are plausible enough to test routing quality.
3. **Rule leakage**
   - `rule_keywords` are metadata for the deterministic baseline; they should not contain an answer that would be unavailable in a real routing scenario.
4. **Distribution coverage**
   - Skill, Tool and Intent labels are all represented in both Validation and Test.
   - Intent contains both same-intent and different-intent cases.
5. **Hard negatives**
   - Add topic-same / intent-different pairs.
   - Add topic-different / intent-same pairs where applicable.
6. **Source provenance**
   - When replacing synthetic cases with real examples, add the source/session/reference metadata.

Do not report the synthetic dataset itself as evidence of model quality. Use it to establish the benchmark pipeline, then replace or annotate cases with human-reviewed Ground Truth.

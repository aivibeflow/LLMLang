# RT-34 query lower bounds, queue amortization and live entries

**Date** 2026-11-25 · **Plan** §2.0, CX-08–11 · **Issue** [#412](https://github.com/aivibeflow/LLMLang/issues/412)

For Boolean existence over an unindexed input of length `n`, the model charges individual coordinate reads. A deterministic correct evaluator must follow the same all-zero execution when every coordinate in that execution's transcript has the same value. If a coordinate is absent, an input with its sole true value at that coordinate has the same transcript and requires the opposite answer. Lean establishes that every coordinate occurs in the all-zero transcript, then uses the length of the duplicate-free coordinate list to prove at least `n` reads. An ascending scan is correct and has an `n`-read schedule, so the matched worst-case bound is exact in this model. The premise covers deterministic adaptive algorithms whose observations consist of coordinate values. Precomputed summaries, packed word instructions and approximate randomized answers use different models.

| Query check, sizes 0–12 | Count |
| --- | ---: |
| Scans compared with Boolean existence | 8,191 |
| Candidate queried coordinate sets | 8,191 |
| Unread-coordinate pairs with equal observations and opposite required answers | 45,057 |

The separate FIFO model charges one primitive per enqueue or dequeue and two primitives for moving an entry from the incoming stack to the outgoing stack. Lean checks each potential-adjusted step and proves `actual cost + final potential ≤ 3 × operation count + initial potential` for every legal history. The potential equals twice the incoming stack length. The Python replay compares FIFO outputs and complete queue state against an independent deque on all 1,912 legal histories of length at most 12. It checks 20,837 operation occurrences. Individual costs exceed three in 2,744 occurrences and reach 23, even though the empty-start total bound holds for every prefix. Warm-start controls with 1–12 entries need the initial potential for the first dequeue.

Live memory counts logical entries in both stacks and a temporary moved entry. The move preserves the number of entries at each intermediate state in the scope of the model. A copy-then-release variant reaches twice the previous live count with the same FIFO output and remaining contents. All 12 warm-start controls distinguish these profiles. These entry counts describe the abstract storage model. Physical allocation, element size, reserved capacity, and target stack usage remain separate questions.

Eight Lean propositions were checked with an axiom audit allowing only `propext`, `Classical.choice` and `Quot.sound`. The lower bound is an exact theorem for the stated query assumptions. The queue result is a sequence bound with explicit initialization. General model matching, reductions, automatic potential inference, stack and allocator analysis and independent benchmark adjudication remain open.

Reproduce with Lean 4.36.0 and Python from the repository root.

```bash
study=research/formal-verification/RT-34/READ-LOWER-AND-QUEUE-01
python "$study/run.py" | cmp "$study/evidence.json" -
```

Two independent Lean and Python replays produced byte-identical ledgers.

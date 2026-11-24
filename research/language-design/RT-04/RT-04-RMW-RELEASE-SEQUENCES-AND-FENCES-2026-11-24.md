# RT-04 atomic RMW, release sequences and fence placement

Atomic fetch-add requires the preceding modification in the per-location order. Relaxed RMW can carry an earlier release to a later acquire even though the RMW itself has no acquire semantics. A release and acquire fence pair orders the surrounding data only when the flag operations are in the required positions and the load reads from the publication or its release sequence.

## Bounded candidate

The fixture extends the [atomic load/store execution relations](RESEARCH-SCENARIO-118-ATOMIC-EXECUTION-RELATIONS.md) with modulo-256 fetch-add, release sequences and release/acquire fences. All shared accesses in the fixture are atomic. The candidate enumerates modification-order permutations and read-from sources, derives synchronization through contiguous RMW successors and takes the transitive closure of sequenced-before and synchronization. It checks coherence for every read and write component of a read-modify-write. A separate question asks whether the same operations can be placed in one total interleaving in which each read sees the latest modification.

A separate SMT encoding uses integer ranks for modifications and sources, the modulo write-value equation, rank intervals with no intervening plain writes, and an irreflexive transitive happens-before relation that contains the required edges. Existential closure suffices because adding edges can only introduce additional coherence restrictions. The one-interleaving check adds a single set of distinct event positions with latest-predecessor constraints. The enumerator and both solvers agree on 167 complete candidate observation tuples across 15 layouts for each of the two questions, for 668 solver verdicts in total. The runner additionally checks 18 named observations and records concrete witnesses when admitted.

The admitted fence cases use a load as the observing operation. The reference uses the C++20 draft's definitions of coherence, RMW predecessors, contiguous RMW release sequences, and its three fence synchronization rules. A global interleaving witness is a separate property of this fixture. Language-wide sequentially consistent ordering, non-atomic races and mixed access sizes remain open. [C++20 working draft, release sequences](https://github.com/cplusplus/draft/blob/6aea7f6be0895b9dd361c6562bdee2f3809e4fa0/source/basic.tex#L5849-L5863) · [RMW and atomic order](https://github.com/cplusplus/draft/blob/6aea7f6be0895b9dd361c6562bdee2f3809e4fa0/source/atomics.tex#L411-L555) · [Fence rules](https://github.com/cplusplus/draft/blob/6aea7f6be0895b9dd361c6562bdee2f3809e4fa0/source/atomics.tex#L3622-L3648).

| Discriminator | Result |
| --- | --- |
| Two fetch-adds from the same initial value | Forbidden with a predecessor check. Allowing arbitrary earlier writes admits both reads returning zero and has no matching global execution. |
| Fetch-add at 255 | The RMW reads 255 and its successor can observe the wrapped zero. |
| Release store, relaxed RMW, acquire observer | Reading the RMW's new flag value forbids a stale payload. Relaxing the observer's load admits it. |
| Plain store between a release head and the observed RMW | Ends that release sequence. The observer can read the RMW's new value and the initial payload. |
| Release fence to acquire load, release store to acquire fence, and both fences | Each properly linked candidate forbids the stale payload. The fence pair also works when the reader observes a later relaxed RMW in the sequence. |
| Move the release fence after the publication, move the acquire fence before the observing load, or omit it | Each control admits the stale payload and has no matching global interleaving for that observation. |
| Acquire-release RMW reads a release | Its following data read cannot see the stale value. The relaxed RMW control admits it. |

A candidate that always requires one global interleaving rules out some permitted weak outcomes. A release/acquire candidate needs to preserve read-from identity, the RMW predecessor and the exact fence placement to distinguish the verified controls. Backend correspondence still needs exact IR and linked target observations. [Atomic lowering obligations](../../compiler-and-translation/RT-13/RESEARCH-SCENARIO-116-ATOMIC-BACKEND-LOWERING-OBLIGATIONS.md).

## Reproduction

The recorded run uses Z3 4.13.3 and cvc5 1.4.2. [Complete outcome domains, formula hashes and witnesses](atomic-rmw-fences/results.json).

```sh
python3 -B research/language-design/RT-04/atomic-rmw-fences/run.py --output /tmp/llmlang-rmw-fences.json
cmp /tmp/llmlang-rmw-fences.json research/language-design/RT-04/atomic-rmw-fences/results.json
```

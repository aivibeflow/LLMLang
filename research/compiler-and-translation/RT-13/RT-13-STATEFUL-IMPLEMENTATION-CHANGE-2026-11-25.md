# RT-13 stateful implementation changes and future traces

Two implementations can agree on the current return value and diverge after a state transfer. This study checks a stateful operation contract against a provider that stores a balance directly and one that stores total credits and debits. A change of provider occurs between invocations and preserves the state visible to the operation. The earlier native replacement experiment supplies separate evidence about retaining an in-flight provider. [Native replacement study](RT-13-STATIC-AND-RUNTIME-BINDING-2026-11-25.md)

The reference exposes credit, debit and balance-reading commands. A credit reports its amount. A debit reports its amount when funds are sufficient and otherwise refuses without changing the balance. The split provider's invariant is that debits are at most credits. Its abstract balance is the difference. Migration captures that balance and initializes either the direct representation or a split representation with zero debits. Internal historical totals are outside the modeled contract. A variant in which those totals are observable needs a stronger transfer relation.

```mermaid
flowchart LR
    A["Old provider state"] --> B["Extract abstract balance"]
    B --> C["Initialize new representation"]
    C --> D["Continue with equal abstract state"]
    D --> E["Match future credit, debit and read observations"]
```

## Checked results

Lean proves that migration preserves the abstract state and that each concrete execution preserves the reference reply and next state. Induction then proves equality of the visible trace for every finite command and switch sequence. The migration theorem depends on `propext`. Step and trace theorems depend on `propext` and `Quot.sound`. The model uses mathematical natural numbers and explicit representation invariants. [Lean model](STATEFUL-IMPLEMENTATION-CHANGE-01/Migration.lean)

The finite driver checks all sequences of length zero through four over eight actions and four initial states. It compares each trace and final abstract state against a separate reference. All 18,724 correct comparisons agree. A seeded migration that resets the balance differs in 8,524 traces. In a delayed-divergence control, credit 4, switch provider, and credit 1 produce the same two visible credit replies in both routes. The following debit of 5 succeeds only with preserved state.

| Observation | Preserving migration | Seeded reset |
| --- | --- | --- |
| Credit 4 | Credited 4 | Credited 4 |
| Switch to split representation | No operation reply | No operation reply |
| Credit 1 | Credited 1 | Credited 1 |
| Debit 5 | Debited 5 | Refused |

For a selection change under the same contract identity, retain the old observation model, verify the new artifact's execution relation, and require a state-transfer receipt for the exact checkpoint and both representations. A verified migration can support a semantically invisible change under that scope. Concurrent state transfer, crash safety, bounded numeric storage, external effects, receipt trust and visibility of implementation identity remain separate obligations. [Evidence](STATEFUL-IMPLEMENTATION-CHANGE-01/evidence.json)

## Reproduction

Use Lean 4.36.0 at revision `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` and CPython 3.12.14.

```sh
study=research/compiler-and-translation/RT-13/STATEFUL-IMPLEMENTATION-CHANGE-01
build=$(mktemp -d)
for seed in 37 75; do
  LC_ALL=C PYTHONHASHSEED="$seed" python "$study/run.py" --lean /path/to/lean \
    --output "$build/result-$seed.json"
done
cmp "$build/result-37.json" "$build/result-75.json"
cmp "$build/result-37.json" "$study/evidence.json"
```

[Runner](STATEFUL-IMPLEMENTATION-CHANGE-01/run.py)

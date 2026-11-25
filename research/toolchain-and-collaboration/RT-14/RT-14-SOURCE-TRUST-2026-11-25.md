# RT-14 Knowledge Context source trust and completeness

[LL-026 / #339](https://github.com/aivibeflow/LLMLang/issues/339)

Completeness is a claim about a declared purpose at a pinned snapshot. The verifier takes a purpose-specific set of required roles and authorized source locators, their expected revisions, and a finalized inventory. An observation records its source, locator, role, purpose, snapshot, revision, disposition, and value. The check emits the exact inventory digest, the requirements digest, and each role's disposition. The fixture's seal binds the inventory digest to the requested snapshot and purpose.

The project authority supplies the contract. A test may come from the project or the verification authority. An explanatory reference may come from the project or a specifically approved external source. Derived candidates do not satisfy any required role. These are fixture classes and explicit role permissions. In a deployed protocol they would be backed by project admission and authenticated source metadata.

| Disposition | Reason |
| --- | --- |
| Present | An approved locator supplies exact current data and every current authoritative observation agrees. |
| Stale | The role has authorized replies, but they are for the wrong revision. |
| Missing | An approved locator reports current absence and no approved current value contradicts it. |
| Unknown | No contracted source replies for the role. |
| Untrusted | A claimed authoritative reply fails its purpose, snapshot, or locator binding. |
| Conflict | Current authoritative values diverge, or current authoritative presence and absence disagree. |
| Unsealed inventory | The finalization receipt is unavailable or does not bind the observed inventory, snapshot, and purpose. |

The test treats sources within a permitted class set as alternatives. It admits a role when an authorized current value is present in a closed inventory and no other authorized current reply contradicts it. A purpose requiring a report from each source must declare each as a separate obligation. Two sources giving the same value do not produce two required-role credits. Duplicate exact replies leave the inventory identity unchanged.

## Observations

CPython 3.12.14 and SQLite 3.53.1 exercised 144 scenarios in 2,648 distinct insertion orders, using exact role dispositions as the expected outcomes. The same inventory had the same digest and decision under each ordering. Forty-eight orders returned complete, 1,276 returned incomplete, and 1,324 returned unsealed. A role-presence check returned 2,600 false completions, including explicit absence accompanied by a derived suggestion and a report for an earlier revision.

Nine additional controls separated exact duplicate replies, omitted or changed sealed data, seals for a different purpose or snapshot, agreement between current authorized locators, disagreement, current contradictory presence and absence, and an unregistered locator. Reusing a seal after removing a source or replacing its value fails even when the remaining SQL rows are valid. An exact matching seal still permits an incomplete result if a role is stale, missing, unknown, untrusted, or conflicting.

This is a temporary SQLite model using a simulated finalization authority and an in-process authority registry. A deployed verifier needs a trusted issuer, authenticated locator-to-object evidence, requirements and requester policy binding, an authoritative means of enumerating the inventory, and a disclosure rule for diagnostics. The fixture cannot detect an omission deliberately accepted by its finalization authority, establish that a list of requirements is adequate for a real task, or establish atomic cross-service finalization.

## Reproduce

Run from the repository root. [Model](SOURCE-TRUST-01/run.py) · [Recorded decisions](SOURCE-TRUST-01/evidence.json)

```sh
python -B research/toolchain-and-collaboration/RT-14/SOURCE-TRUST-01/run.py /tmp/rt14-trust-replay.json
cmp /tmp/rt14-trust-replay.json research/toolchain-and-collaboration/RT-14/SOURCE-TRUST-01/evidence.json
```

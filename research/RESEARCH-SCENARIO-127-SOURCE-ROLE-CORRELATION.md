# Research Scenario 127 — Source Correlation Across FFI Role Checks

**Status:** bounded source analysis with an independent finite oracle

**Research areas:** RT-03 execution · RT-04 ownership and effects · RT-10 runtime and FFI

**Updated:** 2026-11-20

## Question

How much information about aliases must a checker retain to prove compatibility across two FFI calls? Scenario 126 checks shared and exclusive roles on known identities. Scenario 108 shows that joining aliases independently can invent infeasible routes. This experiment applies that comparison at a call boundary where the first call can leave a reservation live. [Multi-resource FFI roles](RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md) · [Path-sensitive alias precision](RESEARCH-SCENARIO-108-PATH-SENSITIVE-ALIAS-PRECISION.md)

## Source fragment and proof rule

The adapter lowers a Python-shaped fixture using declarations of three distinct connection identities `a`, `b`, and `c`, two immutable Boolean inputs `p` and `q`, and an external reference that can denote any of the three connections. The grammar admits local aliases, conditional selection of a reference, two backup starts, and at most one unconditional or conditional finish between them. The existing backup contract requires a shared source and exclusive destination on distinct identities. An accepted start grants the roles, and finish consumes the first reservation before the second check. In this fragment those transitions succeed once the role precondition passes. [Source adapter](PROTOTYPES/RT-04-01/rt04_backup_source_roles.py) · [Role contract](PROTOTYPES/RT-04-01/rt04_backup_roles.py)

```python
backup(a if p else b, b if p else a)
backup(a if p else b, c)
```

The example admits both calls on each value of `p`. The second call shares the first call's source and selects a distinct destination. Keeping both pairs independently adds a synthetic combination where the second source is the first destination. Keeping each role independently also introduces a synthetic first call with the same connection in both roles.

The checker certifies a program only when each route in its representation admits both starts. The comparison uses three representations of the same inputs.

| Representation | Facts retained at the call boundary |
|---|---|
| Separate role sets | The possible identities of each of four arguments, and whether the first reservation can remain live, independently. |
| Pair of roles per call | Both arguments of each call together. The second call's pair is associated with whether finish ran. The first and second records combine independently. |
| Complete route | Both identity pairs and whether the first reservation remains live, correlated by the same inputs. |

## Results

Eight expressions at each argument position and three finish variants give 12,288 programs. Four Boolean assignments and three external identities give 147,456 concrete inputs. Tests compare the parsed role pairs, finish state, and resulting live reservations with an oracle defined directly from those inputs. Each wider representation contains every route of the more precise representation. [Generated corpus and oracle](PROTOTYPES/RT-04-01/test_rt04_backup_source_roles.py)

| Representation | Programs certified for every input |
|---|---:|
| Separate role sets | 156 |
| Pair of roles per call | 214 |
| Complete route | 232 |

Retaining pairs recovered 58 programs. Retaining the relationship across calls recovered another 18. A conditional finish also matters. For `backup(a, b)` followed by a finish only when `p` holds, a second destination `b if p else c` is safe on both branches. The second call's pair and finish state must stay associated to prove it.

A guard using the actual identities admits both calls on 33,464 concrete inputs. It declines the first call on 56,064 and declines the second on 57,928. A refusal preserves the reservations that were live on entry to that check. The model also confirms that reassigning a local alias after the first call leaves the recorded reservation on the original connection.

## Implications for candidate comparison

The contract needs distinctness and compatibility facts over identities, with live reservations captured at the producing call. Independent alias sets can still supply a conservative proof. Retaining only relationships used by a role contract can recover more static admissions. Where the static facts allow both outcomes, a checked call can validate the actual roles and return the earlier live obligations on refusal. Its runtime still needs an acquisition discipline through the point of authorization. [Reservation scheduling](RESEARCH-SCENARIO-126-MULTI-RESOURCE-FFI-ROLES.md)

## Reproduction and scope

```sh
python -B -m unittest discover -s research/PROTOTYPES/RT-04-01 -p 'test_rt04_backup_source_roles.py' -v
```

The checks ran on Python 3.12.14. Complete routes are enumerated over the declared finite input domain. The experiment tests role admission, source binding, and ownership at refusal. Foreign errors after admission, alias escape, loops, arbitrary external identities, actual native concurrency, and the cost of retaining symbolic relationships at production scale remain open.

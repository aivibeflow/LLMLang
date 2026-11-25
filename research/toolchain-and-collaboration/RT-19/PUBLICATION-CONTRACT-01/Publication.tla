---- MODULE Publication ----
EXTENDS FiniteSets

CONSTANT Mode
VARIABLES live, witnessed, seen, online, rights, journal, released, violations

Targets == {"alpha", "beta"}
Rights == {"observe", "append", "seal"}
Values == {"old", "new", "other"}
vars == <<live, witnessed, seen, online, rights, journal, released, violations>>

Init ==
    /\ live = [target \in Targets |-> "old"]
    /\ witnessed = {}
    /\ seen = {}
    /\ online = Targets
    /\ rights = Rights
    /\ journal = "absent"
    /\ released = FALSE
    /\ violations = {}

Prepare ==
    /\ journal = "absent"
    /\ {"observe", "append"} \subseteq rights
    /\ journal' = "pending"
    /\ UNCHANGED <<live, witnessed, seen, online, rights, released, violations>>

Append(target) ==
    /\ journal = "pending"
    /\ ~released
    /\ target \in online \ witnessed
    /\ "observe" \in rights
    /\ ("append" \in rights \/ Mode = "UnfencedAppend")
    /\ (live[target] = "old" \/ Mode = "OverwriteDiverged")
    /\ live' = [live EXCEPT ![target] = "new"]
    /\ witnessed' = witnessed \cup {target}
    /\ violations' = violations
          \cup (IF "append" \in rights THEN {} ELSE {"append-without-authority"})
          \cup (IF live[target] = "old" THEN {} ELSE {"overwrote-divergence"})
    /\ UNCHANGED <<seen, online, rights, journal, released>>

Probe(target) ==
    /\ journal = "pending"
    /\ ~released
    /\ "observe" \in rights
    /\ target \in online
    /\ live[target] = "new"
    /\ (target \in witnessed \/ Mode = "RawTipOnly")
    /\ seen' = seen \cup {target}
    /\ UNCHANGED <<live, witnessed, online, rights, journal, released, violations>>

Seal ==
    /\ journal = "pending"
    /\ ~released
    /\ "observe" \in rights
    /\ ("seal" \in rights \/ Mode = "UnfencedSeal")
    /\ seen = Targets
    /\ released' = TRUE
    /\ violations' = violations \cup (IF "seal" \in rights THEN {} ELSE {"seal-without-authority"})
    /\ UNCHANGED <<live, witnessed, seen, online, rights, journal>>

Settle ==
    /\ journal = "pending"
    /\ "observe" \in rights
    /\ (released \/ Mode = "SpeculativeSettle")
    /\ journal' = "settled"
    /\ UNCHANGED <<live, witnessed, seen, online, rights, released, violations>>

Outside(target, value) ==
    /\ live' = [live EXCEPT ![target] = value]
    /\ UNCHANGED <<witnessed, seen, online, rights, journal, released, violations>>

ChangeRights(fresh) ==
    /\ rights' = fresh
    /\ UNCHANGED <<live, witnessed, seen, online, journal, released, violations>>

ChangeAvailability(fresh) ==
    /\ online' = fresh
    /\ UNCHANGED <<live, witnessed, seen, rights, journal, released, violations>>

Crash ==
    /\ seen' = {}
    /\ UNCHANGED <<live, witnessed, online, rights, journal, released, violations>>

Next ==
    \/ Prepare
    \/ \E target \in Targets: Append(target) \/ Probe(target)
    \/ Seal
    \/ Settle
    \/ \E target \in Targets, value \in Values: Outside(target, value)
    \/ \E fresh \in SUBSET Rights: ChangeRights(fresh)
    \/ \E fresh \in SUBSET Targets: ChangeAvailability(fresh)
    \/ Crash

TypeOK ==
    /\ live \in [Targets -> Values]
    /\ witnessed \subseteq Targets
    /\ seen \subseteq Targets
    /\ online \subseteq Targets
    /\ rights \subseteq Rights
    /\ journal \in {"absent", "pending", "settled"}
    /\ released \in BOOLEAN
    /\ violations \subseteq {"append-without-authority", "seal-without-authority", "overwrote-divergence"}

AuthorizedAndCompared == violations = {}
ObservedWitnesses == seen \subseteq witnessed
ReleaseHasWitnesses == released => witnessed = Targets
SettleHasRelease == journal = "settled" => released
NeverSettled == journal /= "settled"
ReleasedPairIsCurrent == released => \A target \in Targets: live[target] = "new"
====

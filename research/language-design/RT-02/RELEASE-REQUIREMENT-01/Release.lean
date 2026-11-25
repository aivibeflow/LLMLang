namespace ReleaseFixture

inductive Role where
  | release
  | observe
  deriving DecidableEq, Repr

structure Request where
  operation : Nat
  workspace : Nat
  artifact : Nat
  revision : Nat
  payload : Nat
  deriving DecidableEq, Repr

structure Grant where
  principal : Nat
  workspace : Nat
  artifact : Nat
  revision : Nat
  epoch : Nat
  role : Role
  deriving DecidableEq, Repr

inductive Outcome where
  | released
  | replayed
  | conflict
  | denied
  deriving DecidableEq, Repr

def Bound (caller epoch : Nat) (request : Request) (grant : Grant) (role : Role) : Prop :=
  grant.principal = caller ∧ grant.workspace = request.workspace ∧
  grant.artifact = request.artifact ∧ grant.revision = request.revision ∧
  grant.epoch = epoch ∧ grant.role = role

instance (caller epoch : Nat) (request : Request) (grant : Grant) (role : Role) :
    Decidable (Bound caller epoch request grant role) := by
  unfold Bound
  infer_instance

def gate (caller epoch : Nat) (request : Request) (grant : Option Grant)
    (prior : Option Request) : Outcome :=
  match grant, prior with
  | none, _ => .denied
  | some grant, none =>
      if Bound caller epoch request grant .release then .released else .denied
  | some grant, some prior =>
      if Bound caller epoch request grant .observe then
        if prior = request then .replayed else .conflict
      else .denied

def effectCount : Outcome → Nat
  | .released => 1
  | .replayed => 0
  | .conflict => 0
  | .denied => 0

theorem exactRelease (caller epoch : Nat) (request : Request) (grant : Grant) :
    gate caller epoch request (some grant) none = .released ↔
      Bound caller epoch request grant .release := by
  change (if Bound caller epoch request grant .release then Outcome.released else .denied) = _ ↔ _
  constructor
  · intro outcome
    by_cases permission : Bound caller epoch request grant .release
    · exact permission
    · rw [ite_eq_right permission] at outcome
      cases outcome
  · intro permission
    exact ite_eq_left permission

theorem exactReplay (caller epoch : Nat) (request prior : Request) (grant : Grant) :
    gate caller epoch request (some grant) (some prior) = .replayed ↔
      Bound caller epoch request grant .observe ∧ prior = request := by
  change (if Bound caller epoch request grant .observe then
            if prior = request then Outcome.replayed else .conflict
          else .denied) = _ ↔ _
  constructor
  · intro outcome
    by_cases permission : Bound caller epoch request grant .observe
    · by_cases same : prior = request
      · exact ⟨permission, same⟩
      · rw [ite_eq_left permission, ite_eq_right same] at outcome
        cases outcome
    · rw [ite_eq_right permission] at outcome
      cases outcome
  · intro ⟨permission, same⟩
    rw [ite_eq_left permission, ite_eq_left same]

theorem noRepeatedEffect (caller epoch : Nat) (request prior : Request) (grant : Option Grant) :
    effectCount (gate caller epoch request grant (some prior)) = 0 := by
  refine Option.rec (motive := fun grant =>
    effectCount (gate caller epoch request grant (some prior)) = 0) rfl ?_ grant
  intro value
  by_cases permission : Bound caller epoch request value .observe
  · have admitted : gate caller epoch request (some value) (some prior) =
        (if prior = request then .replayed else .conflict) := ite_eq_left permission
    apply Eq.trans (congrArg effectCount admitted)
    by_cases same : prior = request
    · exact congrArg effectCount (ite_eq_left (t := Outcome.replayed) (e := .conflict) same)
    · exact congrArg effectCount (ite_eq_right (t := Outcome.replayed) (e := .conflict) same)
  · have refused : gate caller epoch request (some value) (some prior) = .denied :=
      ite_eq_right permission
    exact congrArg effectCount refused

theorem staleReleaseDenied (caller epoch : Nat) (request : Request) (grant : Grant)
    (stale : grant.epoch ≠ epoch) :
    gate caller epoch request (some grant) none = .denied := by
  have notBound : ¬ Bound caller epoch request grant .release :=
    fun matchProof => stale matchProof.2.2.2.2.1
  exact ite_eq_right notBound

theorem noUnauthorizedReceiptDisclosure (caller epoch : Nat) (request prior : Request)
    (grant : Grant) (denied : ¬ Bound caller epoch request grant .observe) :
    gate caller epoch request (some grant) (some prior) = .denied :=
  ite_eq_right denied

#print axioms exactRelease
#print axioms exactReplay
#print axioms noRepeatedEffect
#print axioms staleReleaseDenied
#print axioms noUnauthorizedReceiptDisclosure

def seedRequest : Request := ⟨11, 13, 17, 19, 29⟩

def changed (mask field value : Nat) : Nat :=
  if mask.testBit field then value + 1 else value

def priorAt (mask : Nat) : Request :=
  ⟨changed mask 0 11, changed mask 1 13, changed mask 2 17, changed mask 3 19, changed mask 4 29⟩

def grantAt (mask : Nat) (role : Role) : Grant :=
  ⟨changed mask 0 31, changed mask 1 13, changed mask 2 17, changed mask 3 19,
   changed mask 4 37, role⟩

def code : Outcome → Nat
  | .denied => 0
  | .released => 1
  | .replayed => 2
  | .conflict => 3

def allCases : List Nat :=
  let grants := none :: (List.range 32).flatMap
    (fun mask => [some (grantAt mask .release), some (grantAt mask .observe)])
  let prior := none :: (List.range 32).map (fun mask => some (priorAt mask))
  grants.flatMap (fun grant => prior.map (fun stored => code (gate 31 37 seedRequest grant stored)))

end ReleaseFixture

def main : IO Unit :=
  IO.println (String.intercalate "," (ReleaseFixture.allCases.map toString))

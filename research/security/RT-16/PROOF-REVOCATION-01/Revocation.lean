set_option autoImplicit false

inductive Scope
  | signer (id : Nat)
  | checker (id : Nat)
  | implementation (id : Nat)

structure Receipt where
  signer : Nat
  checker : Nat
  implementation : Nat
  issued : Nat
  subject : Nat
  receiptId : Nat

structure Revocation where
  scope : Scope
  observedAt : Nat
  effectiveFrom : Nat

def targets (scope : Scope) (receipt : Receipt) : Prop :=
  match scope with
  | .signer id => receipt.signer = id
  | .checker id => receipt.checker = id
  | .implementation id => receipt.implementation = id

def revoked (events : List Revocation) (receipt : Receipt) (view : Nat) : Prop :=
  ∃ event ∈ events, event.observedAt ≤ view ∧ event.effectiveFrom ≤ receipt.issued ∧
    targets event.scope receipt

theorem revocation_persists
    (events : List Revocation) (receipt : Receipt) (first later : Nat)
    (ordered : first ≤ later) (denied : revoked events receipt first) :
    revoked events receipt later := by
  obtain ⟨event, member, visible, effective, matched⟩ := denied
  exact ⟨event, member, Nat.le_trans visible ordered, effective, matched⟩

theorem unseen_event_does_not_apply
    (event : Revocation) (receipt : Receipt) (view : Nat)
    (unseen : view < event.observedAt) :
    ¬ revoked [event] receipt view := by
  intro denied
  obtain ⟨found, member, visible, _, _⟩ := denied
  have same : found = event := by simpa using member
  subst found
  exact (Nat.not_le_of_gt unseen) visible

theorem issuance_before_cutoff_is_unaffected
    (event : Revocation) (receipt : Receipt) (view : Nat)
    (earlier : receipt.issued < event.effectiveFrom) :
    ¬ revoked [event] receipt view := by
  intro denied
  obtain ⟨found, member, _, effective, _⟩ := denied
  have same : found = event := by simpa using member
  subst found
  exact (Nat.not_le_of_gt earlier) effective

def supported (subject : Nat) (receiptId : Nat) (receipt : Receipt) : Prop :=
  subject = receipt.subject ∧ receiptId = receipt.receiptId

theorem replacement_does_not_validate_old_dependency
    (subject oldId : Nat) (replacement : Receipt)
    (distinct : oldId ≠ replacement.receiptId) :
    ¬ supported subject oldId replacement := by
  intro exactSupport
  exact distinct exactSupport.2

#print axioms revocation_persists
#print axioms unseen_event_does_not_apply
#print axioms issuance_before_cutoff_is_unaffected
#print axioms replacement_does_not_validate_old_dependency

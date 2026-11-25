import Lean

namespace RecordOwnership

def acquired (fails : α → Bool) (order : List α) : List α :=
  order.takeWhile fun field => !fails field

def abortRelease (fails : α → Bool) (order : List α) : List α :=
  (acquired fails order).reverse

def isMoved [DecidableEq α] (move : Option α) (field : α) : Bool :=
  decide (some field = move)

def recordRelease [DecidableEq α] (move : Option α) (declaration : List α) : List α :=
  declaration.filter fun field => !isMoved move field

def transferredRelease [DecidableEq α] (move : Option α) (declaration : List α) : List α :=
  declaration.filter (isMoved move)

def completedRelease [DecidableEq α] (move : Option α) (declaration : List α) : List α :=
  recordRelease move declaration ++ transferredRelease move declaration

theorem acquiredSublist (fails : α → Bool) (order : List α) :
    (acquired fails order).Sublist order :=
  List.takeWhile_sublist _

theorem acquiredCannotFail (fails : α → Bool) {order : List α} {slot : α}
    (member : slot ∈ acquired fails order) : fails slot = false := by
  induction order with
  | nil => simp [acquired] at member
  | cons first rest ih =>
    cases status : fails first with
    | false =>
      simp [acquired, status] at member
      cases member with
      | inl same => simpa [same] using status
      | inr inside => exact ih inside
    | true => simp [acquired, status] at member

theorem abortConservesAcquired (fails : α → Bool) (order : List α) :
    (abortRelease fails order).Perm (acquired fails order) :=
  List.reverse_perm _

theorem abortReleasesOnce (fails : α → Bool) {order : List α} (distinct : order.Nodup) :
    (abortRelease fails order).Nodup :=
  (abortConservesAcquired fails order).symm.nodup ((acquiredSublist fails order).nodup distinct)

theorem abortNeverReleasesAFailedSlot (fails : α → Bool) {order : List α} {slot : α}
    (member : slot ∈ abortRelease fails order) : fails slot = false :=
  acquiredCannotFail fails (List.mem_reverse.mp member)

theorem completionConservesDeclared [DecidableEq α] (move : Option α) (declaration : List α) :
    (completedRelease move declaration).Perm declaration := by
  simpa [completedRelease, recordRelease, transferredRelease] using
    List.filter_append_perm (fun field => !isMoved move field) declaration

theorem completionConservesAcquired [DecidableEq α] (move : Option α)
    {declaration initialization : List α} (schema : declaration.Perm initialization) :
    (completedRelease move declaration).Perm initialization :=
  (completionConservesDeclared move declaration).trans schema

theorem completionReleasesOnce [DecidableEq α] (move : Option α)
    {declaration initialization : List α} (schema : declaration.Perm initialization)
    (distinct : initialization.Nodup) : (completedRelease move declaration).Nodup :=
  (completionConservesAcquired move schema).symm.nodup distinct

theorem movedSlotAbsentFromRecord [DecidableEq α] (slot : α) (declaration : List α) :
    slot ∉ recordRelease (some slot) declaration := by
  simp [recordRelease, isMoved, List.mem_filter]

theorem transferredSlotSingleton [DecidableEq α] {slot : α} {declaration : List α}
    (distinct : declaration.Nodup) (owned : slot ∈ declaration) :
    transferredRelease (some slot) declaration = [slot] := by
  induction declaration with
  | nil => simp at owned
  | cons first rest ih =>
    have tail := (List.nodup_cons.mp distinct).2
    by_cases same : first = slot
    · subst first
      have absent := (List.nodup_cons.mp distinct).1
      have empty : transferredRelease (some slot) rest = [] := by
        apply List.filter_eq_nil_iff.mpr
        intro field member
        simp only [isMoved, Option.some.injEq, decide_eq_true_eq]
        intro identity
        exact absent (identity ▸ member)
      change List.filter (isMoved (some slot)) rest = [] at empty
      simp only [transferredRelease]
      have keep : isMoved (some slot) slot = true := by simp [isMoved]
      rw [List.filter_cons_of_pos keep, empty]
    · have member : slot ∈ rest := by
        simpa [Ne.symm same] using owned
      have one := ih tail member
      change List.filter (isMoved (some slot)) rest = [slot] at one
      simp only [transferredRelease]
      have reject : ¬ isMoved (some slot) first := by simp [isMoved, same]
      rw [List.filter_cons_of_neg reject, one]

theorem absentSlotCannotBeReleased [DecidableEq α] {slot : α} {declaration : List α}
    (absent : slot ∉ declaration) : transferredRelease (some slot) declaration = [] := by
  apply List.filter_eq_nil_iff.mpr
  intro field member
  simp only [isMoved, Option.some.injEq, decide_eq_true_eq]
  intro identity
  exact absent (identity ▸ member)

theorem duplicateDeclarationRepeatsRelease :
    completedRelease (some 0) [0, 0] = [0, 0] := by decide

theorem mismatchedDeclarationsCanInventRelease :
    completedRelease none [0, 2] = [0, 2] ∧
      ¬ (completedRelease (α := Nat) none [0, 2]).Perm [0, 1] := by decide

theorem oppositeCompletionOrdersDistinguishTrace :
    completedRelease (α := Nat) none [0, 1] ≠ completedRelease none [1, 0] := by decide

def attempt (slot : Nat) : Int := Int.ofNat (slot + 1)
def successfulAcquire (slot : Nat) : Int := Int.ofNat (slot + 11)
def release (slot : Nat) : Int := -(Int.ofNat (slot + 1))

def execute (declaration initialization : List Nat) (mask : Nat) (move : Option Nat) : Nat × List Int :=
  let acquiredSlots := acquired mask.testBit initialization
  let acquisitionEvents := acquiredSlots.flatMap fun slot => [attempt slot, successfulAcquire slot]
  match initialization.drop acquiredSlots.length with
  | failed :: _ =>
    (failed + 1, acquisitionEvents ++ [attempt failed] ++ (abortRelease mask.testBit initialization).map release)
  | [] =>
    let record := (recordRelease move declaration).map release
    let transferred := (transferredRelease move declaration).map release
    (0, acquisitionEvents ++ [30] ++ record ++ [40] ++ transferred)

#print axioms acquiredSublist
#print axioms acquiredCannotFail
#print axioms abortConservesAcquired
#print axioms abortReleasesOnce
#print axioms abortNeverReleasesAFailedSlot
#print axioms completionConservesDeclared
#print axioms completionConservesAcquired
#print axioms completionReleasesOnce
#print axioms movedSlotAbsentFromRecord
#print axioms transferredSlotSingleton
#print axioms absentSlotCannotBeReleased
#print axioms duplicateDeclarationRepeatsRelease
#print axioms mismatchedDeclarationsCanInventRelease
#print axioms oppositeCompletionOrdersDistinguishTrace

end RecordOwnership

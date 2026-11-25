set_option autoImplicit false

structure Profile where
  operation : Nat
  target : Nat
  abi : Nat
  runtime : Nat
  capabilityScope : Nat
  policy : Nat
  observations : Nat
  deriving DecidableEq

structure Receipt where
  profile : Profile
  artifact : Nat
  checked : Bool
  deriving DecidableEq

structure Implementation where
  profile : Profile
  artifact : Nat
  available : Bool
  receipt : Option Receipt
  deriving DecidableEq

def eligible (request : Profile) (impl : Implementation) : Bool :=
  impl.available && decide (impl.profile = request) &&
    decide (impl.receipt = some ⟨request, impl.artifact, true⟩)

def select (request : Profile) : List Implementation → Option Implementation
  | [] => none
  | head :: tail =>
    if eligible request head then some head else select request tail

theorem selected_from_eligible
    (request : Profile) (choices : List Implementation) (result : Implementation)
    (selected : select request choices = some result) :
    result ∈ choices ∧ eligible request result = true := by
  induction choices with
  | nil => simp [select] at selected
  | cons head tail ih =>
    by_cases ready : eligible request head = true
    · have same : head = result := by simpa [select, ready] using selected
      subst result
      exact ⟨List.mem_cons_self, ready⟩
    · have rest : select request tail = some result := by
        simpa [select, ready] using selected
      obtain ⟨member, verified⟩ := ih rest
      exact ⟨List.mem_cons_of_mem head member, verified⟩

theorem no_selection_iff_none_eligible (request : Profile) (choices : List Implementation) :
    select request choices = none ↔ ∀ choice ∈ choices, eligible request choice = false := by
  induction choices with
  | nil => simp [select]
  | cons head tail ih =>
    cases h : eligible request head <;> simp [select, h, ih]

theorem selection_binds_exact_evidence
    (request : Profile) (choices : List Implementation) (result : Implementation)
    (selected : select request choices = some result) :
    result.available = true ∧ result.profile = request ∧
      result.receipt = some ⟨request, result.artifact, true⟩ := by
  have checked := (selected_from_eligible request choices result selected).2
  simpa [eligible, and_assoc] using checked

theorem eligible_preferred_stays_selected
    (request : Profile) (preferred : Implementation) (fallbacks : List Implementation)
    (h : eligible request preferred = true) :
    select request (preferred :: fallbacks) = some preferred := by
  simp [select, h]

#print axioms selected_from_eligible
#print axioms no_selection_iff_none_eligible
#print axioms selection_binds_exact_evidence
#print axioms eligible_preferred_stays_selected

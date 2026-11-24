namespace ModularCaller

abbrev Outcome := Int × List String
abbrev Provider := Int → Option Outcome

def providerContract (input : Int) (observed : Outcome) : Prop :=
  (observed.1 = input + 1 ∨ observed.1 = input + 2) ∧
    observed.2 = ["first", "last"]

def callerContract (input : Int) (observed : Outcome) : Prop :=
  (observed.1 = (input + 1) + 10 ∨ observed.1 = (input + 2) + 10) ∧
    observed.2 = ["before", "first", "last", "after"]

def caller (provider : Provider) (input : Int) : Option Outcome :=
  (provider input).map fun (value, trace) => (value + 10, "before" :: trace ++ ["after"])

def Satisfies (member : Provider) (contract : Int → Outcome → Prop) : Prop :=
  ∀ input, ∃ observed, member input = some observed ∧ contract input observed

theorem reusableCaller (provider : Provider) (valid : Satisfies provider providerContract) :
    Satisfies (caller provider) callerContract := by
  intro input
  obtain ⟨⟨value, trace⟩, observed, values, ordered⟩ := valid input
  refine ⟨(value + 10, "before" :: trace ++ ["after"]), ?_, ?_⟩
  · unfold caller
    rw [observed]
    rfl
  · change trace = ["first", "last"] at ordered
    refine ⟨?_, congrArg (fun xs => "before" :: xs ++ ["after"]) ordered⟩
    rcases values with valueOne | valueTwo
    · exact Or.inl (congrArg (· + 10) valueOne)
    · exact Or.inr (congrArg (· + 10) valueTwo)

def primary (input : Int) : Option Outcome := some (input + 1, ["first", "last"])
def alternate (input : Int) : Option Outcome := some (input + 2, ["first", "last"])
def reordered (input : Int) : Option Outcome := some (input + 1, ["last", "first"])
def outOfRange (input : Int) : Option Outcome := some (input + 3, ["first", "last"])
def missing (_ : Int) : Option Outcome := none

theorem primaryValid : Satisfies primary providerContract := by
  intro input
  exact ⟨(input + 1, ["first", "last"]), rfl, Or.inl rfl, rfl⟩

theorem alternateValid : Satisfies alternate providerContract := by
  intro input
  exact ⟨(input + 2, ["first", "last"]), rfl, Or.inr rfl, rfl⟩

theorem reboundCaller : Satisfies (caller alternate) callerContract :=
  reusableCaller alternate alternateValid

theorem primaryCaller : Satisfies (caller primary) callerContract :=
  reusableCaller primary primaryValid

theorem rejectsReordered : ¬ Satisfies reordered providerContract := by
  intro valid
  obtain ⟨observed, actual, allowed⟩ := valid 0
  have exactObservation : ((0 : Int) + 1, ["last", "first"]) = observed :=
    Option.some.inj actual
  rw [← exactObservation] at allowed
  revert allowed
  unfold providerContract
  decide

theorem rejectsOutOfRange : ¬ Satisfies outOfRange providerContract := by
  intro valid
  obtain ⟨observed, actual, allowed⟩ := valid 0
  have exactObservation : ((0 : Int) + 3, ["first", "last"]) = observed :=
    Option.some.inj actual
  rw [← exactObservation] at allowed
  revert allowed
  unfold providerContract
  decide

theorem rejectsMissing : ¬ Satisfies missing providerContract := by
  intro valid
  obtain ⟨observed, actual, _⟩ := valid 0
  contradiction

#print axioms reusableCaller
#print axioms primaryCaller
#print axioms reboundCaller
#print axioms rejectsReordered
#print axioms rejectsOutOfRange
#print axioms rejectsMissing

end ModularCaller

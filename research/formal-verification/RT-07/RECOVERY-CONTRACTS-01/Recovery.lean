namespace RecoveryContracts

inductive ErrorCode
  | retry | fatal

inductive Stop
  | done (state : Nat)
  | error (code : ErrorCode) (state : Nat)
  | cancelled (state : Nat)
  | diverged

structure Observation where
  stop : Stop
  trace : List Nat

abbrev Primary := Nat → Observation → Prop
abbrev Handler := ErrorCode → Nat → Observation → Prop

def Invoked (primary : Primary) (handles : ErrorCode → Bool) (initial : Nat)
    (code : ErrorCode) (state : Nat) : Prop :=
  handles code = true ∧ ∃ trace, primary initial ⟨.error code state, trace⟩

def Handoff (primary : Primary) (handles : ErrorCode → Bool)
    (handlerPre : ErrorCode → Nat → Prop) (initial : Nat) : Prop :=
  ∀ code state trace, handles code = true →
    primary initial ⟨.error code state, trace⟩ → handlerPre code state

theorem handoffExact (primary : Primary) (handles : ErrorCode → Bool)
    (handlerPre : ErrorCode → Nat → Prop) (initial : Nat) :
    Handoff primary handles handlerPre initial ↔
      (∀ code state, Invoked primary handles initial code state → handlerPre code state) :=
  ⟨fun valid code state ⟨enabled, trace, prior⟩ => valid code state trace enabled prior,
   fun valid code state trace enabled prior => valid code state ⟨enabled, trace, prior⟩⟩

inductive Recover (primary : Primary) (handler : Handler) (handles : ErrorCode → Bool)
    (initial : Nat) : Observation → Prop where
  | done {state trace} :
      primary initial ⟨.done state, trace⟩ →
      Recover primary handler handles initial ⟨.done state, trace⟩
  | passError {code state trace} :
      handles code = false → primary initial ⟨.error code state, trace⟩ →
      Recover primary handler handles initial ⟨.error code state, trace⟩
  | cancelled {state trace} :
      primary initial ⟨.cancelled state, trace⟩ →
      Recover primary handler handles initial ⟨.cancelled state, trace⟩
  | diverged {trace} :
      primary initial ⟨.diverged, trace⟩ →
      Recover primary handler handles initial ⟨.diverged, trace⟩
  | handled {code state trace result} :
      handles code = true → primary initial ⟨.error code state, trace⟩ →
      handler code state result →
      Recover primary handler handles initial ⟨result.stop, trace ++ result.trace⟩

theorem recoverMonotone {small large : Primary} {fewer more : Handler}
    {handles : ErrorCode → Bool} {initial : Nat} {result : Observation}
    (primaryIncluded : ∀ s o, small s o → large s o)
    (handlerIncluded : ∀ c s o, fewer c s o → more c s o)
    (run : Recover small fewer handles initial result) :
    Recover large more handles initial result := by
  cases run with
  | done prior => exact .done (primaryIncluded _ _ prior)
  | passError disabled prior => exact .passError disabled (primaryIncluded _ _ prior)
  | cancelled prior => exact .cancelled (primaryIncluded _ _ prior)
  | diverged prior => exact .diverged (primaryIncluded _ _ prior)
  | handled enabled prior next =>
    exact .handled enabled (primaryIncluded _ _ prior) (handlerIncluded _ _ _ next)

theorem primaryCancelPasses {primary : Primary} {handler : Handler} {handles : ErrorCode → Bool}
    {initial state : Nat} {trace : List Nat}
    (occurred : primary initial ⟨.cancelled state, trace⟩) :
    Recover primary handler handles initial ⟨.cancelled state, trace⟩ :=
  .cancelled occurred

#print axioms handoffExact
#print axioms recoverMonotone
#print axioms primaryCancelPasses

end RecoveryContracts

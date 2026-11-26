import Std.Tactic

set_option autoImplicit false

namespace LinuxSyscalls

inductive Outcome where
  | abiViolation
  | progress (value : Int)
  -- Zero bytes from a nonempty read. The descriptor determines its meaning.
  | eof
  | errno (value : Int)
  deriving DecidableEq

def decode (reading : Bool) (raw count : Int) : Outcome :=
  if -4095 ≤ raw ∧ raw < 0 then .errno (-raw)
  else if raw < 0 ∨ count < raw then .abiViolation
  else if reading = true ∧ raw = 0 ∧ count > 0 then .eof
  else .progress raw

def kernelEnvelope (raw count : Int) : Prop :=
  (-4095 ≤ raw ∧ raw < 0) ∨ (0 ≤ raw ∧ raw ≤ count)

def providerOutcome (reading : Bool) (raw count : Int) : Outcome → Prop
  | .abiViolation => ¬kernelEnvelope raw count
  | .progress value => 0 ≤ raw ∧ raw ≤ count ∧
      ¬(reading = true ∧ raw = 0 ∧ count > 0) ∧ value = raw
  | .eof => reading = true ∧ raw = 0 ∧ count > 0
  | .errno value => -4095 ≤ raw ∧ raw < 0 ∧ value = -raw

def publicOutcome (reading : Bool) (count : Int) : Outcome → Prop
  | .abiViolation => False
  | .progress value => 0 ≤ value ∧ value ≤ count ∧
      ¬(reading = true ∧ count > 0 ∧ value = 0)
  | .eof => reading = true ∧ count > 0
  | .errno value => 1 ≤ value ∧ value ≤ 4095

theorem decoderConformance (reading : Bool) (raw count : Int) :
    providerOutcome reading raw count (decode reading raw count) := by
  unfold decode
  split <;> rename_i bound
  · exact ⟨bound.1, bound.2, rfl⟩
  split <;> rename_i outside
  · change ¬kernelEnvelope raw count
    unfold kernelEnvelope
    omega
  split <;> rename_i zeroRead
  · exact zeroRead
  · change 0 ≤ raw ∧ raw ≤ count ∧ _
    exact ⟨by omega, by omega, zeroRead, rfl⟩

theorem publicRefinement (reading : Bool) (raw count : Int) (outcome : Outcome)
    (kernel : kernelEnvelope raw count)
    (provider : providerOutcome reading raw count outcome) :
    publicOutcome reading count outcome := by
  cases outcome with
  | abiViolation => exact provider kernel
  | progress value =>
    rcases provider with ⟨lower, upper, nonEof, rfl⟩
    exact ⟨lower, upper, fun ⟨read, positive, zero⟩ => nonEof ⟨read, zero, positive⟩⟩
  | eof => exact ⟨provider.1, provider.2.2⟩
  | errno value =>
    rcases provider with ⟨lower, upper, rfl⟩
    exact ⟨by omega, by omega⟩

theorem decodedPublicOutcome (reading : Bool) (raw count : Int)
    (kernel : kernelEnvelope raw count) : publicOutcome reading count (decode reading raw count) :=
  publicRefinement reading raw count _ kernel (decoderConformance reading raw count)

example : ¬providerOutcome true (-4) 5 (.progress 4) := by
  simp [providerOutcome]
example : providerOutcome true (-4096) 5 .abiViolation ∧ ¬publicOutcome true 5 .abiViolation :=
  by simp [providerOutcome, publicOutcome, kernelEnvelope]

end LinuxSyscalls

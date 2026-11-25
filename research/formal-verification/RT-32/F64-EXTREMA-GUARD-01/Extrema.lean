import Lean

namespace F64Extrema

abbrev Word := BitVec 64
abbrev Result := Word × Word

def positiveZero : Word := 0
def negativeZero : Word := 0x8000000000000000
def canonicalNaN : Word := 0x7ff8000000000000

def magnitude (word : Word) : Nat := (word &&& 0x7fffffffffffffff).toNat

def isNaN (word : Word) : Bool := decide (0x7ff0000000000000 < magnitude word)

def isSignaling (word : Word) : Bool :=
  isNaN word && (word &&& 0x0008000000000000) == 0

def isZero (word : Word) : Bool := word == positiveZero || word == negativeZero

def bothZero (left right : Word) : Bool := isZero left && isZero right

def normalizeResult (word : Word) : Word := if isNaN word then canonicalNaN else word

def key (word : Word) : Nat :=
  if 0x8000000000000000 ≤ word.toNat then 0xffffffffffffffff - word.toNat
  else 0x8000000000000000 + word.toNat

def ordered (left right : Word) : Result :=
  if key left ≤ key right then (left, right) else (right, left)

def repeated (word : Word) : Result := (word, word)

def nanPair : Result := repeated canonicalNaN

def signedZeroExtrema : Result := (negativeZero, positiveZero)

inductive Rule where
  | propagate
  | preferNumber
  | preferNumberLeft
  | preferNumberRight
  | orderedLeft
  | unorderedRight
  | propagateSignalingRight

def oneNaN (rule : Rule) (left right : Word) (leftIsNaN : Bool) : Result :=
  let number := if leftIsNaN then right else left
  let nan := if leftIsNaN then left else right
  match rule with
  | .propagate => nanPair
  | .orderedLeft => if leftIsNaN then nanPair else repeated left
  | .unorderedRight => if leftIsNaN then repeated right else nanPair
  | .propagateSignalingRight => if isSignaling nan then nanPair else repeated number
  | _ => repeated number

def zeroTie (rule : Rule) (left right : Word) : Result :=
  match rule with
  | .preferNumberLeft | .orderedLeft => repeated left
  | .preferNumberRight | .unorderedRight | .propagateSignalingRight => repeated right
  | _ => signedZeroExtrema

def evaluate (rule : Rule) (left right : Word) : Result :=
  if isNaN left then
    if isNaN right then nanPair else oneNaN rule left right true
  else if isNaN right then oneNaN rule left right false
  else if left = right then repeated left
  else if bothZero left right then zeroTie rule left right
  else ordered left right

def agreementGuard (left right : Word) : Bool :=
  (isNaN left && isNaN right) ||
    (!isNaN left && !isNaN right && (left == right || !bothZero left right))

def allAgree (left right : Word) : Prop :=
  ∀ rule : Rule, evaluate rule left right = evaluate .propagate left right

@[simp] theorem canonicalIsNaN : isNaN canonicalNaN = true := rfl

theorem nonNaNDistinct {word : Word} (ordinary : isNaN word = false) : word ≠ canonicalNaN := by
  intro equal
  simp [equal] at ordinary

theorem diagonalDiffersFromSignedZero (word : Word) : repeated word ≠ signedZeroExtrema := by
  intro equal
  have left : word = negativeZero := congrArg Prod.fst equal
  have right : word = positiveZero := congrArg Prod.snd equal
  exact (by decide : negativeZero ≠ positiveZero) (left.symm.trans right)

theorem agreementGuardComplete (left right : Word) :
    allAgree left right ↔ agreementGuard left right = true := by
  cases leftNaN : isNaN left <;> cases rightNaN : isNaN right
  · by_cases same : left = right
    · simp [allAgree, agreementGuard, evaluate, rightNaN, same]
    · cases tied : bothZero left right
      · simp [allAgree, agreementGuard, evaluate, leftNaN, rightNaN, same, tied]
      · simp [allAgree, agreementGuard, evaluate, leftNaN, rightNaN, same, tied]
        exact ⟨.orderedLeft, diagonalDiffersFromSignedZero left⟩
  · simp [allAgree, agreementGuard, evaluate, leftNaN, rightNaN]
    refine ⟨.preferNumber, ?_⟩
    intro equal
    exact nonNaNDistinct leftNaN (congrArg Prod.fst equal)
  · simp [allAgree, agreementGuard, evaluate, leftNaN, rightNaN]
    refine ⟨.preferNumber, ?_⟩
    intro equal
    exact nonNaNDistinct rightNaN (congrArg Prod.fst equal)
  · simp [allAgree, agreementGuard, evaluate, leftNaN, rightNaN]

theorem guardedSubstitution (left right : Word) (admitted : agreementGuard left right = true)
    (source target : Rule) : evaluate source left right = evaluate target left right := by
  have universal := (agreementGuardComplete left right).mpr admitted
  exact (universal source).trans (universal target).symm

theorem outsideHasDistinguishingRule (left right : Word) (refused : agreementGuard left right = false) :
    ∃ rule : Rule, evaluate rule left right ≠ evaluate .propagate left right := by
  have impossible : ¬ allAgree left right := by
    intro agreements
    have contradiction := (agreementGuardComplete left right).mp agreements
    simp [refused] at contradiction
  simpa [allAgree] using impossible

theorem zeroOrderWitness :
    evaluate .propagate positiveZero negativeZero = signedZeroExtrema ∧
      evaluate .preferNumberLeft positiveZero negativeZero = repeated positiveZero := ⟨rfl, rfl⟩

theorem oneNaNWitness :
    evaluate .propagate canonicalNaN 0x3ff0000000000000 = nanPair ∧
      evaluate .preferNumber canonicalNaN 0x3ff0000000000000 = repeated 0x3ff0000000000000 := ⟨rfl, rfl⟩

theorem twoNaNsAgree : agreementGuard canonicalNaN 0xfff0000000000100 = true := rfl

#print axioms canonicalIsNaN
#print axioms nonNaNDistinct
#print axioms diagonalDiffersFromSignedZero
#print axioms agreementGuardComplete
#print axioms guardedSubstitution
#print axioms outsideHasDistinguishingRule
#print axioms zeroOrderWitness
#print axioms oneNaNWitness
#print axioms twoNaNsAgree

end F64Extrema

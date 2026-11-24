import TransitionState

/- Symbolic correspondence for the register-state observation model. -/
namespace TransitionState.Symbolic

mutual
  inductive Term where
    | literal (value : Int)
    | input (index : Nat)
    | add (left right : Term)
    | sub (left right : Term)
    | choose (guard : Predicate) (yes no : Term)

  inductive Predicate where
    | eq (left right : Term)
    | le (left right : Term)
    | and (left right : Predicate)
    | or (left right : Predicate)
    | not (value : Predicate)
end

mutual
  def evalTerm (input : Registers) : Term → Int
    | .literal value => value
    | .input index => input[index]?.getD 0
    | .add left right => evalTerm input left + evalTerm input right
    | .sub left right => evalTerm input left - evalTerm input right
    | .choose guard yes no =>
        if evalPredicate input guard then evalTerm input yes else evalTerm input no

  def evalPredicate (input : Registers) : Predicate → Bool
    | .eq left right => evalTerm input left == evalTerm input right
    | .le left right => decide (evalTerm input left ≤ evalTerm input right)
    | .and left right => evalPredicate input left && evalPredicate input right
    | .or left right => evalPredicate input left || evalPredicate input right
    | .not value => !evalPredicate input value
end

abbrev Symbols := List Term

def evaluate (input : Registers) (symbols : Symbols) : Registers :=
  symbols.map (evalTerm input)

def readInt (symbols : Symbols) : IntExpr → Term
  | .literal value => .literal value
  | .register index => symbols[index]?.getD (.literal 0)
  | .add left right => .add (readInt symbols left) (readInt symbols right)
  | .sub left right => .sub (readInt symbols left) (readInt symbols right)

def readBool (symbols : Symbols) : BoolExpr → Predicate
  | .eq left right => .eq (readInt symbols left) (readInt symbols right)
  | .le left right => .le (readInt symbols left) (readInt symbols right)
  | .and left right => .and (readBool symbols left) (readBool symbols right)
  | .or left right => .or (readBool symbols left) (readBool symbols right)
  | .not value => .not (readBool symbols value)

def select (guard : Predicate) (yes no : Symbols) : Symbols :=
  List.zipWith (Term.choose guard) yes no

def compile (symbols : Symbols) : Program → Symbols
  | .done => symbols
  | .assign index value rest =>
      compile (symbols.set index (readInt symbols value)) rest
  | .branch guard yes no rest =>
      compile (select (readBool symbols guard) (compile symbols yes) (compile symbols no)) rest

def compileTrace (symbols : Symbols) : List Program → List Symbols
  | [] => []
  | action :: trace =>
      let next := compile symbols action
      next :: compileTrace next trace

theorem readInt_correct (input : Registers) (symbols : Symbols) (expr : IntExpr) :
    evalTerm input (readInt symbols expr) = evalInt (evaluate input symbols) expr := by
  induction expr with
  | literal value => rfl
  | register index =>
      simp only [readInt, evalInt, evaluate, List.getElem?_map]
      cases symbols[index]? <;> rfl
  | add left right ihLeft ihRight =>
      simp [readInt, evalTerm, evalInt, ihLeft, ihRight]
  | sub left right ihLeft ihRight =>
      simp [readInt, evalTerm, evalInt, ihLeft, ihRight]

theorem readBool_correct (input : Registers) (symbols : Symbols) (expr : BoolExpr) :
    evalPredicate input (readBool symbols expr) = evalBool (evaluate input symbols) expr := by
  induction expr <;> simp_all [readBool, evalPredicate, evalBool, readInt_correct]

theorem compile_length (symbols : Symbols) (program : Program) :
    (compile symbols program).length = symbols.length := by
  induction program generalizing symbols with
  | done => rfl
  | assign index value rest ih =>
      simp [compile, ih, List.length_set]
  | branch guard yes no rest ihYes ihNo ihRest =>
      simp [compile, select, ihYes, ihNo, ihRest, List.length_zipWith]

theorem select_correct (input : Registers) (guard : Predicate) (yes no : Symbols)
    (sameLength : yes.length = no.length) :
    evaluate input (select guard yes no) =
      if evalPredicate input guard then evaluate input yes else evaluate input no := by
  induction yes generalizing no with
  | nil => cases no <;> simp_all [select, evaluate]
  | cons head tail ih =>
      cases no with
      | nil => simp at sameLength
      | cons other rest =>
          simp only [List.length_cons, Nat.succ.injEq] at sameLength
          have step := ih rest sameLength
          cases branch : evalPredicate input guard <;>
            simp_all [select, evaluate, evalTerm]

theorem evaluate_set (input : Registers) (symbols : Symbols) (index : Nat) (value : Term) :
    evaluate input (symbols.set index value) = (evaluate input symbols).set index (evalTerm input value) :=
  List.map_set

theorem compile_correct (input : Registers) (symbols : Symbols) (program : Program) :
    evaluate input (compile symbols program) = run (evaluate input symbols) program := by
  induction program generalizing symbols with
  | done => rfl
  | assign index value rest ih =>
      rw [compile, ih, run, evaluate_set, readInt_correct]
  | branch guard yes no rest ihYes ihNo ihRest =>
      rw [compile, ihRest, run]
      rw [select_correct input _ _ _ (by simp [compile_length])]
      rw [readBool_correct, ihYes, ihNo]

theorem compileTrace_correct (input : Registers) (symbols : Symbols) (trace : List Program) :
    (compileTrace symbols trace).map (evaluate input) = observe (evaluate input symbols) trace := by
  induction trace generalizing symbols with
  | nil => rfl
  | cons action rest ih =>
      simp [compileTrace, observe, ih, compile_correct]

def initialSymbols (count : Nat) : Symbols :=
  List.ofFn (fun index : Fin count => Term.input index)

theorem evaluate_initial (input : Registers) :
    evaluate input (initialSymbols input.length) = input := by
  apply List.ext_getElem
  · simp [evaluate, initialSymbols]
  · intro i _ h
    simp [evaluate, initialSymbols, evalTerm, List.getElem?_eq_getElem h]

/-- Evaluation of compiled terms agrees with every source action boundary,
    for every concrete initial register vector and action list. -/
theorem correspondence (input : Registers) (trace : List Program) :
    (compileTrace (initialSymbols input.length) trace).map (evaluate input) =
      observe input trace := by
  rw [compileTrace_correct, evaluate_initial]

#print axioms correspondence

end TransitionState.Symbolic

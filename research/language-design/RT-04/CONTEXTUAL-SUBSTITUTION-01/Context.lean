namespace ContextualSubstitution

inductive Client (Input Seen : Type) where
  | done (answer : Seen)
  | call (input : Input) (next : Seen → Client Input Seen)

def execute (provider : Input → Seen) : Client Input Seen → Seen
  | .done answer => answer
  | .call input next => execute provider (next (provider input))

theorem equalInAllClients (left right : Input → Seen) :
    (∀ input, left input = right input) ↔
      (∀ client, execute left client = execute right client) := by
  constructor
  · intro equal client
    induction client with
    | done answer => rfl
    | call input next compatible =>
      change execute left (next (left input)) = execute right (next (right input))
      rw [equal input]
      exact compatible (right input)
  · intro contextual input
    exact contextual (.call input .done)

def plain (input : Bool) : Bool × Bool := (input, false)
def tagged (input : Bool) : Bool × Bool := (input, true)

theorem sameValueInAllValueClients (client : Client Bool Bool) :
    execute (fun input => (plain input).1) client = execute (fun input => (tagged input).1) client :=
  (equalInAllClients _ _).mp (fun _ => rfl) client

theorem completeClientDistinguishes :
    execute plain (.call false .done) ≠ execute tagged (.call false .done) := by decide

#print axioms equalInAllClients
#print axioms sameValueInAllValueClients
#print axioms completeClientDistinguishes

end ContextualSubstitution

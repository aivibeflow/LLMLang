namespace CacheTrial

def step (n : Nat) : Nat := n + 0

def Claim : Prop := ∀ n : Nat, step n = n

end CacheTrial

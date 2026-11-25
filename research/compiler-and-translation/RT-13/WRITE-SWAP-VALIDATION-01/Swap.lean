namespace WriteSwap

structure Write where
  slot : Nat
  value : Int
  visible : Bool

abbrev Heap := Nat → Int
abbrev Event := Nat × Int

def store (heap : Heap) (write : Write) (slot : Nat) : Int :=
  if slot = write.slot then write.value else heap slot

def events (write : Write) : List Event :=
  if write.visible then [(write.slot, write.value)] else []

def sameFinalHeap (a b : Write) (heap : Heap) : Prop :=
  ∀ slot, store (store heap a) b slot = store (store heap b) a slot

theorem sameHeap_iff (a b : Write) (heap : Heap) :
    sameFinalHeap a b heap ↔ a.slot ≠ b.slot ∨ a.value = b.value := by
  constructor
  · intro same
    by_cases loc : a.slot = b.slot
    · right
      have observed := same a.slot
      simpa [store, loc] using observed.symm
    · exact Or.inl loc
  · intro guard slot
    by_cases loc : a.slot = b.slot
    · have values : a.value = b.value := guard.resolve_left (fun different => different loc)
      simp [store, loc, values]
    · by_cases first : slot = a.slot
      · simp [store, first, loc]
      · by_cases second : slot = b.slot
        · simp [store, second, Ne.symm loc]
        · simp [store, first, second]

theorem sameEvents_iff (a b : Write) :
    events a ++ events b = events b ++ events a ↔
      a.visible = false ∨ b.visible = false ∨ (a.slot = b.slot ∧ a.value = b.value) := by
  rcases a with ⟨aSlot, aVal, aPublic⟩
  rcases b with ⟨bSlot, bVal, bPublic⟩
  cases aPublic <;> cases bPublic <;>
    simp [events, and_comm, eq_comm]

def safeSwap (a b : Write) : Prop :=
  (a.slot ≠ b.slot ∨ a.value = b.value) ∧
  (a.visible = false ∨ b.visible = false ∨ (a.slot = b.slot ∧ a.value = b.value))

theorem swap_iff (a b : Write) (heap : Heap) :
    (sameFinalHeap a b heap ∧ events a ++ events b = events b ++ events a) ↔
      safeSwap a b := by
  rw [safeSwap, sameHeap_iff, sameEvents_iff]

#print axioms sameHeap_iff
#print axioms sameEvents_iff
#print axioms swap_iff

end WriteSwap

import Lean

namespace SignedCodec

abbrev PairBytes := BitVec 8 × BitVec 8
abbrev QuadBytes := PairBytes × PairBytes
abbrev EightBytes := QuadBytes × QuadBytes

def splitHalves {width : Nat} (bits : BitVec (width + width)) :
    BitVec width × BitVec width :=
  (bits.extractLsb' width width, bits.extractLsb' 0 width)

def joinHalves {width : Nat} (halves : BitVec width × BitVec width) :
    BitVec (width + width) :=
  halves.1 ++ halves.2

@[simp] theorem joinSplit {width : Nat} (bits : BitVec (width + width)) :
    joinHalves (splitHalves bits) = bits := by
  simp [joinHalves, splitHalves]

@[simp] theorem splitJoin {width : Nat} (halves : BitVec width × BitVec width) :
    splitHalves (joinHalves halves) = halves := by
  rcases halves with ⟨high, low⟩
  simp [splitHalves, joinHalves, BitVec.extractLsb'_append_eq_left, BitVec.extractLsb'_append_eq_right]

def unpack32 (word : BitVec 32) : QuadBytes :=
  let (high, low) := splitHalves (width := 16) word
  (splitHalves high, splitHalves low)

def pack32 (bytes : QuadBytes) : BitVec 32 :=
  joinHalves (joinHalves bytes.1, joinHalves bytes.2)

def unpack64 (word : BitVec 64) : EightBytes :=
  let (high, low) := splitHalves (width := 32) word
  (unpack32 high, unpack32 low)

def pack64 (bytes : EightBytes) : BitVec 64 :=
  joinHalves (pack32 bytes.1, pack32 bytes.2)

@[simp] theorem packUnpack32 (word : BitVec 32) :
    pack32 (unpack32 word) = word := by
  simp only [pack32, unpack32, joinSplit, Prod.eta]

@[simp] theorem unpackPack32 (bytes : QuadBytes) :
    unpack32 (pack32 bytes) = bytes := by
  rcases bytes with ⟨high, low⟩
  simp [pack32, unpack32]

@[simp] theorem packUnpack64 (word : BitVec 64) :
    pack64 (unpack64 word) = word := by
  simp only [pack64, unpack64, packUnpack32, Prod.eta, joinSplit]

@[simp] theorem unpackPack64 (bytes : EightBytes) :
    unpack64 (pack64 bytes) = bytes := by
  rcases bytes with ⟨high, low⟩
  simp [pack64, unpack64]

def lower : Int := -(2 ^ 63)
def upperExclusive : Int := 2 ^ 63

def admissible (value : Int) : Prop := lower ≤ value ∧ value < upperExclusive

instance (value : Int) : Decidable (admissible value) :=
  inferInstanceAs (Decidable (lower ≤ value ∧ value < upperExclusive))

def encode (value : Int) : EightBytes := unpack64 (BitVec.ofInt 64 value)

def decode (bytes : EightBytes) : Int := (pack64 bytes).toInt

def encodeChecked (value : Int) : Option EightBytes :=
  if admissible value then some (encode value) else none

theorem signedRoundTrip {value : Int} (range : admissible value) :
    decode (encode value) = value := by
  rcases range with ⟨left, right⟩
  simp only [decode, encode, packUnpack64]
  exact BitVec.toInt_ofInt_eq_self (by decide) left right

theorem wordDecodesInRange (bytes : EightBytes) :
    admissible (decode bytes) := by
  unfold admissible decode lower upperExclusive
  exact ⟨BitVec.le_toInt (pack64 bytes), BitVec.toInt_lt (x := pack64 bytes)⟩

theorem bytesRoundTrip (bytes : EightBytes) : encode (decode bytes) = bytes := by
  simp [encode, decode]

theorem admittedEncodingInjective {left right : Int}
    (leftRange : admissible left) (rightRange : admissible right)
    (equalBytes : encode left = encode right) : left = right := by
  have equal := congrArg decode equalBytes
  simpa only [signedRoundTrip leftRange, signedRoundTrip rightRange] using equal

theorem rejectsOutsideSignedRange {value : Int} (outside : ¬ admissible value) :
    encodeChecked value = none := by
  simp [encodeChecked, outside]

theorem checkedBytesRoundTrip (bytes : EightBytes) :
    encodeChecked (decode bytes) = some bytes := by
  simp [encodeChecked, wordDecodesInRange, bytesRoundTrip]

def octets (bytes : EightBytes) : List Nat :=
  [bytes.1.1.1.toNat, bytes.1.1.2.toNat, bytes.1.2.1.toNat, bytes.1.2.2.toNat,
   bytes.2.1.1.toNat, bytes.2.1.2.toNat, bytes.2.2.1.toNat, bytes.2.2.2.toNat]

def replay (value : Int) : Option (List Nat × Int) :=
  (encodeChecked value).map fun bytes => (octets bytes, decode bytes)

theorem uncheckedUpperAliasesLower :
    encode upperExclusive = encode lower ∧ encodeChecked upperExclusive = none := by decide

theorem networkByteOrderMatters :
    decode (((1, 0), (0, 0)), ((0, 0), (0, 0))) = 72057594037927936 ∧
      decode (((0, 0), (0, 0)), ((0, 0), (0, 1))) = 1 := by decide

#print axioms joinSplit
#print axioms splitJoin
#print axioms packUnpack32
#print axioms unpackPack32
#print axioms packUnpack64
#print axioms unpackPack64
#print axioms signedRoundTrip
#print axioms wordDecodesInRange
#print axioms bytesRoundTrip
#print axioms admittedEncodingInjective
#print axioms rejectsOutsideSignedRange
#print axioms checkedBytesRoundTrip
#print axioms uncheckedUpperAliasesLower
#print axioms networkByteOrderMatters

end SignedCodec

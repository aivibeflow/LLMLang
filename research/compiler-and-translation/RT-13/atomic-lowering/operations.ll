define i8 @inc_monotonic(ptr %counter, i8 %delta) {
  %previous = atomicrmw add ptr %counter, i8 %delta monotonic, align 1
  ret i8 %previous
}

define i8 @inc_acqrel(ptr %counter, i8 %delta) {
  %previous = atomicrmw add ptr %counter, i8 %delta acq_rel, align 1
  ret i8 %previous
}

define i32 @inc_word(ptr %counter, i32 %delta) {
  %previous = atomicrmw add ptr %counter, i32 %delta acq_rel, align 4
  ret i32 %previous
}

define void @publish_fence(ptr %data, ptr %flag, i8 %payload) {
  store atomic i8 %payload, ptr %data monotonic, align 1
  fence release
  store atomic i8 1, ptr %flag monotonic, align 1
  ret void
}

define i16 @read_fence(ptr %flag, ptr %data) {
  %marked = load atomic i8, ptr %flag monotonic, align 1
  fence acquire
  %value = load atomic i8, ptr %data monotonic, align 1
  %high = zext i8 %marked to i16
  %upper = shl i16 %high, 8
  %low = zext i8 %value to i16
  %packed = or i16 %upper, %low
  ret i16 %packed
}

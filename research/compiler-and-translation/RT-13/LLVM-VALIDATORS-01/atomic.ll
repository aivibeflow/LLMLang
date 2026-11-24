target datalayout = "e-p:64:64"

define i16 @src(i8 noundef %seed) {
  %p = alloca i8, align 1
  store i8 %seed, ptr %p, align 1
  %current = atomicrmw add ptr %p, i8 1 acq_rel, align 1
  fence acquire
  %next = load i8, ptr %p, align 1
  %old = zext i8 %current to i16
  %upper = shl i16 %old, 8
  %new = zext i8 %next to i16
  %packed = or i16 %upper, %new
  ret i16 %packed
}
define i16 @tgt(i8 noundef %seed) {
  %p = alloca i8, align 1
  store i8 %seed, ptr %p, align 1
  %current = load i8, ptr %p, align 1
  %incremented = add i8 %current, 1
  store i8 %incremented, ptr %p, align 1
  %next = load i8, ptr %p, align 1
  %old = zext i8 %current to i16
  %upper = shl i16 %old, 8
  %new = zext i8 %next to i16
  %packed = or i16 %upper, %new
  ret i16 %packed
}

; ASSERT EQ: i16 1 = call i16 @src(i8 0)
; ASSERT EQ: i16 1 = call i16 @tgt(i8 0)
; ASSERT EQ: i16 65280 = call i16 @src(i8 255)
; ASSERT EQ: i16 65280 = call i16 @tgt(i8 255)

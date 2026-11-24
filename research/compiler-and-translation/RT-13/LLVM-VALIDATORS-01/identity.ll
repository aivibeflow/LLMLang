target datalayout = "e-p:64:64"

define i8 @src(i8 noundef %input) {
  %r = add i8 %input, 0
  ret i8 %r
}
define i8 @tgt(i8 noundef %input) {
  ret i8 %input
}

; ASSERT EQ: i8 0 = call i8 @src(i8 0)
; ASSERT EQ: i8 0 = call i8 @tgt(i8 0)
; ASSERT EQ: i8 -128 = call i8 @src(i8 -128)
; ASSERT EQ: i8 -128 = call i8 @tgt(i8 -128)

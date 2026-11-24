target datalayout = "e-p:64:64"

define i8 @src(i8 noundef %input) {
  %r = add i8 %input, 1
  ret i8 %r
}
define i8 @tgt(i8 noundef %input) {
  %r = add nsw i8 %input, 1
  ret i8 %r
}

; ASSERT EQ: i8 127 = call i8 @src(i8 126)
; ASSERT EQ: i8 127 = call i8 @tgt(i8 126)
; ASSERT EQ: i8 -128 = call i8 @src(i8 127)
; ASSERT EQ: i8 poison = call i8 @tgt(i8 127)

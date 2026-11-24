target datalayout = "e-p:64:64"

define i8 @src(i8 noundef %value) {
  fence acquire
  ret i8 %value
}
define i8 @tgt(i8 noundef %value) {
  ret i8 %value
}

; ASSERT EQ: i8 42 = call i8 @src(i8 42)
; ASSERT EQ: i8 42 = call i8 @tgt(i8 42)

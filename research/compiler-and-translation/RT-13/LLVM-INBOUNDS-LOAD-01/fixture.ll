target triple = "x86_64-pc-linux-gnu"
target datalayout = "e-m:e-p:64:64:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"

@bytes = private constant [8 x i8] c"LLMprobe"

define i32 @branch_first(i64 %index) {
entry:
  %valid = icmp ult i64 %index, 8
  br i1 %valid, label %read, label %bounds
read:
  %p = getelementptr inbounds i8, ptr @bytes, i64 %index
  %v = load i8, ptr %p, align 1
  %out = zext i8 %v to i32
  ret i32 %out
bounds:
  ret i32 -1
}

define i32 @choose_pointer_first(i64 %index) {
entry:
  %valid = icmp ult i64 %index, 8
  %maybe = getelementptr inbounds i8, ptr @bytes, i64 %index
  %pointer = select i1 %valid, ptr %maybe, ptr @bytes
  %byte = load i8, ptr %pointer, align 1
  %value = zext i8 %byte to i32
  %out = select i1 %valid, i32 %value, i32 -1
  ret i32 %out
}

define i32 @choose_index_first(i64 %index) {
entry:
  %valid = icmp ult i64 %index, 8
  %safe = select i1 %valid, i64 %index, i64 0
  %p = getelementptr inbounds i8, ptr @bytes, i64 %safe
  %v = load i8, ptr %p, align 1
  %value = zext i8 %v to i32
  %out = select i1 %valid, i32 %value, i32 -1
  ret i32 %out
}

define i32 @choose_result_last(i64 %index) {
entry:
  %valid = icmp ult i64 %index, 8
  %p = getelementptr inbounds i8, ptr @bytes, i64 %index
  %v = load i8, ptr %p, align 1
  %value = zext i8 %v to i32
  %out = select i1 %valid, i32 %value, i32 -1
  ret i32 %out
}

define i32 @freeze_pointer(i64 %index) {
entry:
  %valid = icmp ult i64 %index, 8
  %maybe = getelementptr inbounds i8, ptr @bytes, i64 %index
  %p = freeze ptr %maybe
  %v = load i8, ptr %p, align 1
  %value = zext i8 %v to i32
  %out = select i1 %valid, i32 %value, i32 -1
  ret i32 %out
}

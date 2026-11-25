(module
  (memory (export "memory") i64 2 2)
  (func (export "view_byte") (param $base i64) (param $span i64) (param $offset i64) (result i32)
    (local $capacity i64)
    memory.size
    i64.const 16
    i64.shl
    local.set $capacity
    local.get $offset
    local.get $span
    i64.ge_u
    local.get $base
    local.get $capacity
    i64.gt_u
    i32.or
    local.get $span
    local.get $capacity
    local.get $base
    i64.sub
    i64.gt_u
    i32.or
    if
      i32.const -1
      return
    end
    local.get $base
    local.get $offset
    i64.add
    i32.load8_u))

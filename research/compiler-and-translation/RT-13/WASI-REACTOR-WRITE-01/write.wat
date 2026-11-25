(module
  (import "wasi_snapshot_preview1" "fd_write"
    (func $fd_write (param i32 i32 i32 i32) (result i32)))
  (memory (export "memory") 1)
  (global $ready (mut i32) (i32.const 0))
  (func (export "_initialize")
    i32.const 1
    global.set $ready)
  (func (export "emit") (param $fd i32) (param $left i32)
                         (param $right i32) (param $seed i32) (result i32)
    (local $index i32) (local $status i32) (local $written i32)
    global.get $ready
    i32.eqz
    if
      i32.const 16580608
      return
    end
    local.get $left
    i32.const 8
    i32.gt_u
    local.get $right
    i32.const 8
    i32.gt_u
    i32.or
    if
      i32.const 16711680
      return
    end
    (loop $fill
      i32.const 32
      local.get $index
      i32.add
      local.get $seed
      local.get $index
      i32.add
      i32.store8
      i32.const 48
      local.get $index
      i32.add
      local.get $seed
      i32.const 32
      i32.add
      local.get $index
      i32.add
      i32.store8
      local.get $index
      i32.const 1
      i32.add
      local.tee $index
      i32.const 8
      i32.lt_u
      br_if $fill)
    i32.const 0
    i32.const 32
    i32.store
    i32.const 4
    local.get $left
    i32.store
    i32.const 8
    i32.const 48
    i32.store
    i32.const 12
    local.get $right
    i32.store
    i32.const 16
    i32.const 0
    i32.store
    local.get $fd
    i32.const 0
    i32.const 2
    i32.const 16
    call $fd_write
    local.tee $status
    if
      local.get $status
      i32.const 16
      i32.shl
      return
    end
    i32.const 16
    i32.load
    local.tee $written
    local.get $left
    local.get $right
    i32.add
    i32.gt_u
    if
      i32.const 16646144
      return
    end
    local.get $written))

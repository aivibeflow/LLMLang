use cranelift_codegen::ir::{types, AbiParam, InstBuilder, MemFlags, Signature};
use cranelift_codegen::settings::{self, Configurable};
use cranelift_frontend::{FunctionBuilder, FunctionBuilderContext};
use cranelift_jit::{JITBuilder, JITModule};
use cranelift_module::{default_libcall_names, Linkage, Module};
use std::cell::RefCell;
use std::env;
use std::io::{self, BufRead};

type Emit = extern "C" fn(u32);
type Entry = unsafe extern "C" fn(u32, u32, u32, Emit, *mut u32) -> u32;

thread_local! {
    static EVENTS: RefCell<Vec<u32>> = const { RefCell::new(Vec::new()) };
}

extern "C" fn collect(value: u32) {
    EVENTS.with_borrow_mut(|events| events.push(value));
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Policy {
    Preserving,
    DropOverflow,
    ReverseEffects,
    StoreOnError,
}

fn make_entry(
    level: &str,
    policy: Policy,
) -> Result<(JITModule, Entry, String, Vec<u8>), Box<dyn std::error::Error>> {
    let mut settings = settings::builder();
    settings.set("opt_level", level)?;
    settings.set("is_pic", "false")?;
    let isa = cranelift_native::builder_with_options(false)
        .map_err(|error| io::Error::other(error))?
        .finish(settings::Flags::new(settings))?;
    let pointer = isa.pointer_type();
    let system_call = isa.default_call_conv();

    let mut module = JITModule::new(JITBuilder::with_isa(isa, default_libcall_names()));
    let mut sig = Signature::new(system_call);
    for ty in [types::I32, types::I32, types::I32, pointer, pointer] {
        sig.params.push(AbiParam::new(ty));
    }
    sig.returns.push(AbiParam::new(types::I32));
    let id = module.declare_function("checked_add", Linkage::Export, &sig)?;

    let mut context = module.make_context();
    context.func.signature = sig;
    let mut frontend = FunctionBuilderContext::new();
    let mut builder = FunctionBuilder::new(&mut context.func, &mut frontend);
    let entry = builder.create_block();
    let compute = builder.create_block();
    let fail = builder.create_block();
    let success = builder.create_block();
    builder.append_block_params_for_function_params(entry);
    let value = builder.append_block_param(success, types::I32);

    let mut effect = Signature::new(system_call);
    effect.params.push(AbiParam::new(types::I32));
    let callback = builder.import_signature(effect);

    builder.switch_to_block(entry);
    let parameters = builder.block_params(entry);
    let (a, b, enabled, emit, out) = (
        parameters[0],
        parameters[1],
        parameters[2],
        parameters[3],
        parameters[4],
    );
    if policy != Policy::ReverseEffects {
        builder.ins().call_indirect(callback, emit, &[a]);
    }
    builder.ins().brif(enabled, compute, &[], success, &[b]);

    builder.switch_to_block(compute);
    let (sum, overflow) = builder.ins().sadd_overflow(a, b);
    if policy == Policy::DropOverflow {
        builder.ins().jump(success, &[sum]);
    } else {
        builder.ins().brif(overflow, fail, &[], success, &[sum]);
    }

    builder.switch_to_block(fail);
    if policy == Policy::ReverseEffects {
        builder.ins().call_indirect(callback, emit, &[a]);
    }
    if policy == Policy::StoreOnError {
        let zero = builder.ins().iconst(types::I32, 0);
        builder.ins().store(MemFlags::new(), zero, out, 0);
    }
    let one = builder.ins().iconst(types::I32, 1);
    builder.ins().return_(&[one]);

    builder.switch_to_block(success);
    builder.ins().call_indirect(callback, emit, &[value]);
    if policy == Policy::ReverseEffects {
        builder.ins().call_indirect(callback, emit, &[a]);
    }
    builder.ins().store(MemFlags::new(), value, out, 0);
    let zero = builder.ins().iconst(types::I32, 0);
    builder.ins().return_(&[zero]);
    builder.seal_all_blocks();
    builder.finalize();

    let clif = context.func.display().to_string();
    module.define_function(id, &mut context)?;
    let machine = context
        .compiled_code()
        .ok_or_else(|| io::Error::other("Missing compiled code"))?
        .code_buffer()
        .to_vec();
    module.finalize_definitions()?;
    let address = module.get_finalized_function(id);
    // Finalization publishes a readable executable allocation of this exact size.
    let linked = unsafe { std::slice::from_raw_parts(address, machine.len()) };
    if linked != machine.as_slice() {
        return Err("Finalized machine code differs from the compiled buffer".into());
    }
    // The generated signature matches Entry, and module keeps its code alive.
    let entry = unsafe { std::mem::transmute::<*const u8, Entry>(address) };
    Ok((module, entry, clif, machine))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 4 || !matches!(args[0].as_str(), "none" | "speed") {
        return Err("Usage: probe none|speed policy ir-output code-output".into());
    }
    let policy = match args[1].as_str() {
        "preserving" => Policy::Preserving,
        "drop_overflow" => Policy::DropOverflow,
        "reverse_effects" => Policy::ReverseEffects,
        "store_on_error" => Policy::StoreOnError,
        _ => return Err("Unsupported policy".into()),
    };
    let (_module, entry, clif, machine) = make_entry(&args[0], policy)?;
    std::fs::write(&args[2], clif)?;
    std::fs::write(&args[3], machine)?;
    for line in io::stdin().lock().lines() {
        let line = line?;
        let values = line
            .split_whitespace()
            .map(str::parse::<u32>)
            .collect::<Result<Vec<_>, _>>()?;
        let [a, b, enabled] = values.as_slice() else {
            return Err("Expected three unsigned input bit patterns".into());
        };
        let mut slot = 0xabad1234;
        // The output slot is writable/aligned and collect only records the callback value.
        let status = unsafe { entry(*a, *b, *enabled, collect, &mut slot) };
        print!("{status} {slot}");
        EVENTS.with_borrow_mut(|events| {
            for event in events.drain(..) {
                print!(" {event}");
            }
        });
        println!();
    }
    Ok(())
}

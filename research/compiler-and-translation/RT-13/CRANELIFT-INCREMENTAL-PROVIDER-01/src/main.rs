use cranelift_codegen::ir::{types, AbiParam, InstBuilder, Signature};
use cranelift_codegen::settings::{self, Configurable};
use cranelift_frontend::{FunctionBuilder, FunctionBuilderContext};
use cranelift_jit::{JITBuilder, JITModule};
use cranelift_module::{default_libcall_names, FuncId, Linkage, Module, ModuleError};
use std::error::Error;
use std::io;
use std::mem;

type Result<T> = std::result::Result<T, Box<dyn Error>>;
type Unary = unsafe extern "C" fn(u32) -> u32;
type Indirect = unsafe extern "C" fn(u32, *const u8) -> u32;

#[derive(Clone, Copy)]
enum Body {
    Add(i64),
    Direct(FuncId),
    Indirect,
}

struct Code {
    owner: Option<JITModule>,
    entry: *const u8,
    calls_indirectly: bool,
    bytes: Vec<Vec<u8>>,
}

impl Code {
    fn unary(&self, input: u32) -> u32 {
        assert!(!self.calls_indirectly);
        // The selected entry has the unary ABI and its owning module is live.
        let target: Unary = unsafe { mem::transmute(self.entry) };
        unsafe { target(input) }
    }

    fn indirect(&self, input: u32, provider: &Self) -> u32 {
        assert!(self.calls_indirectly && !provider.calls_indirectly);
        // Both owning modules remain borrowed through the call. The provider is unary.
        let target: Indirect = unsafe { mem::transmute(self.entry) };
        unsafe { target(input, provider.entry) }
    }
}

impl Drop for Code {
    fn drop(&mut self) {
        // No entry addresses escape this owner, and each native call borrows it.
        unsafe { self.owner.take().unwrap().free_memory() };
    }
}

fn module(level: &str) -> Result<JITModule> {
    let mut flags = settings::builder();
    flags.set("opt_level", level)?;
    flags.set("is_pic", "false")?;
    let target = cranelift_native::builder_with_options(false)
        .map_err(io::Error::other)?
        .finish(settings::Flags::new(flags))?;
    Ok(JITModule::new(JITBuilder::with_isa(target, default_libcall_names())))
}

fn signature(module: &JITModule, indirect: bool) -> Signature {
    let mut signature = Signature::new(module.isa().default_call_conv());
    signature.params.push(AbiParam::new(types::I32));
    if indirect {
        signature.params.push(AbiParam::new(module.isa().pointer_type()));
    }
    signature.returns.push(AbiParam::new(types::I32));
    signature
}

fn define(
    module: &mut JITModule, id: FuncId, body: Body, actual: Signature,
) -> std::result::Result<Vec<u8>, ModuleError> {
    let mut context = module.make_context();
    context.func.signature = actual;
    let direct = match body {
        Body::Direct(provider) => Some(module.declare_func_in_func(provider, &mut context.func)),
        _ => None,
    };
    let indirect = signature(module, false);
    let mut state = FunctionBuilderContext::new();
    let mut f = FunctionBuilder::new(&mut context.func, &mut state);
    let block = f.create_block();
    f.append_block_params_for_function_params(block);
    f.switch_to_block(block);
    let input = f.block_params(block)[0];
    let result = match body {
        Body::Add(add) => f.ins().iadd_imm(input, add),
        Body::Direct(_) => {
            let call = f.ins().call(direct.unwrap(), &[input]);
            let value = f.inst_results(call)[0];
            f.ins().iadd_imm(value, 1)
        }
        Body::Indirect => {
            let address = f.block_params(block)[1];
            let callback = f.import_signature(indirect);
            let call = f.ins().call_indirect(callback, address, &[input]);
            let value = f.inst_results(call)[0];
            f.ins().iadd_imm(value, 1)
        }
    };
    f.ins().return_(&[result]);
    f.seal_all_blocks();
    f.finalize();
    module.define_function(id, &mut context)?;
    Ok(context.compiled_code().unwrap().code_buffer().to_vec())
}

fn finalize(
    mut owner: JITModule, entry: FuncId, calls_indirectly: bool, bytes: Vec<Vec<u8>>,
) -> Result<Code> {
    owner.finalize_definitions()?;
    let entry = owner.get_finalized_function(entry);
    Ok(Code {
        owner: Some(owner),
        entry,
        calls_indirectly,
        bytes,
    })
}

fn direct(level: &str, addend: i64) -> Result<Code> {
    let mut owner = module(level)?;
    let unary = signature(&owner, false);
    let leaf = owner.declare_function("provider", Linkage::Local, &unary)?;
    let root = owner.declare_function("entry", Linkage::Export, &unary)?;
    let leaf_bytes = define(&mut owner, leaf, Body::Add(addend), unary.clone())?;
    let root_bytes = define(&mut owner, root, Body::Direct(leaf), unary.clone())?;
    let mut code = finalize(owner, root, false, vec![leaf_bytes, root_bytes])?;
    let old_owner = code.owner.as_mut().unwrap();
    let duplicate = define(old_owner, leaf, Body::Add(addend + 100), unary);
    assert!(matches!(duplicate, Err(ModuleError::DuplicateDefinition(_))));
    Ok(code)
}

fn single(level: &str, body: Body) -> Result<Code> {
    let mut owner = module(level)?;
    let signature = signature(&owner, matches!(body, Body::Indirect));
    let entry = owner.declare_function("entry", Linkage::Export, &signature)?;
    let bytes = define(&mut owner, entry, body, signature)?;
    finalize(owner, entry, matches!(body, Body::Indirect), vec![bytes])
}

fn print_code(mode: &str, role: &str, code: &Code) {
    for (index, data) in code.bytes.iter().enumerate() {
        print!("code {mode} {role} {index} ");
        for byte in data {
            print!("{byte:02x}");
        }
        println!();
    }
}

fn main() -> Result<()> {
    for mode in ["none", "speed"] {
        let old_direct = direct(mode, 13)?;
        let new_direct = direct(mode, 29)?;
        let relay = single(mode, Body::Indirect)?;
        let old_provider = single(mode, Body::Add(13))?;
        let new_provider = single(mode, Body::Add(29))?;
        for (name, code) in [
            ("direct-before", &old_direct),
            ("direct-after", &new_direct),
            ("relay", &relay),
            ("provider-before", &old_provider),
            ("provider-after", &new_provider),
        ] {
            print_code(mode, name, code);
        }
        let samples = (0..256).chain([0x7fff_ffff, 0x8000_0000, 0xffff_ffef, 0xffff_ffff]);
        for input in samples {
            println!(
                "values {} {} {} {} {} {}",
                mode,
                input,
                old_direct.unary(input),
                new_direct.unary(input),
                relay.indirect(input, &old_provider),
                relay.indirect(input, &new_provider),
            );
        }
        // Dropping the old direct module and indirect provider frees only old code.
        drop(old_direct);
        drop(old_provider);
        println!("retained {mode} {} {}", new_direct.unary(3), relay.indirect(3, &new_provider));
    }
    Ok(())
}

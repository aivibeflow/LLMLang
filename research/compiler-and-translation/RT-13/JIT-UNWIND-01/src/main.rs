use cranelift_codegen::ir::{types, AbiParam, InstBuilder, SourceLoc};
use cranelift_codegen::isa::unwind::UnwindInfo;
use cranelift_codegen::isa::TargetIsa;
use cranelift_codegen::settings::{self, Configurable};
use cranelift_frontend::{FunctionBuilder, FunctionBuilderContext};
use cranelift_jit::{JITBuilder, JITModule};
use cranelift_module::{default_libcall_names, Linkage, Module};
use gimli::write::{Address, EhFrame, EndianVec, FrameTable};
use gimli::LittleEndian;
use std::{env, io};

type Callback = extern "C" fn(u32) -> u32;
type Entry = unsafe extern "C" fn(u32, Callback) -> u32;

extern "C" {
    fn host_call(entry: Entry, code_size: usize) -> i32;
    fn callback_fde_registered() -> i32;
    fn __register_frame(section: *const u8);
    fn __deregister_frame(section: *const u8);
}

struct RegisteredFrame(Vec<u8>);

impl RegisteredFrame {
    fn new(info: UnwindInfo, isa: &dyn TargetIsa, entry: Entry) -> Result<Self, Box<dyn std::error::Error>> {
        let UnwindInfo::SystemV(info) = info else {
            return Err("expected System V unwind information".into());
        };
        let mut table = FrameTable::default();
        let cie = table.add_cie(isa.create_systemv_cie().ok_or("missing CIE")?);
        table.add_fde(cie, info.to_fde(Address::Constant(entry as usize as u64)));
        let mut section = EhFrame(EndianVec::new(LittleEndian));
        table.write_eh_frame(&mut section)?;
        let mut bytes = section.0.into_vec();
        bytes.extend_from_slice(&[0; 4]); // libgcc expects a zero-length record after the FDE.
        // The buffer stays alive and keeps its address until deregistration in Drop.
        unsafe { __register_frame(bytes.as_ptr()) };
        Ok(Self(bytes))
    }
}

impl Drop for RegisteredFrame {
    fn drop(&mut self) {
        unsafe { __deregister_frame(self.0.as_ptr()) };
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let [level, unwind, registration] = args.as_slice() else {
        return Err("usage: probe none|speed true|false unregistered|registered".into());
    };
    if !matches!((unwind.as_str(), registration.as_str()), ("true" | "false", "unregistered") | ("true", "registered")) {
        return Err("registration requires emitted unwind operations".into());
    }
    let mut settings = settings::builder();
    settings.set("opt_level", level)?;
    settings.set("unwind_info", unwind)?;
    settings.set("preserve_frame_pointers", "true")?;
    let isa = cranelift_native::builder_with_options(false)
        .map_err(io::Error::other)?
        .finish(settings::Flags::new(settings))?;
    let pointer = isa.pointer_type();
    let mut module = JITModule::new(JITBuilder::with_isa(isa, default_libcall_names()));
    let mut sig = module.make_signature();
    sig.params.extend([AbiParam::new(types::I32), AbiParam::new(pointer)]);
    sig.returns.push(AbiParam::new(types::I32));
    let id = module.declare_function("jit_step", Linkage::Export, &sig)?;
    let mut callback = module.make_signature();
    callback.params.push(AbiParam::new(types::I32));
    callback.returns.push(AbiParam::new(types::I32));

    let mut context = module.make_context();
    context.func.signature = sig;
    let mut frontend = FunctionBuilderContext::new();
    let mut builder = FunctionBuilder::new(&mut context.func, &mut frontend);
    let entry = builder.create_block();
    builder.append_block_params_for_function_params(entry);
    builder.switch_to_block(entry);
    let input = builder.block_params(entry)[0];
    let callee = builder.block_params(entry)[1];
    let callback = builder.import_signature(callback);
    builder.set_srcloc(SourceLoc::new(4));
    let call = builder.ins().call_indirect(callback, callee, &[input]);
    let observed = builder.inst_results(call)[0];
    builder.set_srcloc(SourceLoc::new(5));
    let output = builder.ins().iadd_imm(observed, 1);
    builder.ins().return_(&[output]);
    builder.seal_all_blocks();
    builder.finalize();

    module.define_function(id, &mut context)?;
    let compiled = context.compiled_code().ok_or("no machine code")?;
    let unwind_info = compiled.create_unwind_info(module.isa())?;
    let code_size = compiled.code_buffer().len();
    println!("compiled {} {} {code_size}", u8::from(unwind_info.is_some()), compiled.buffer.unwind_info.len());
    for span in compiled.buffer.get_srclocs_sorted() {
        println!("source {} {} {}", span.start, span.end, span.loc.bits());
    }
    module.finalize_definitions()?;
    // The module keeps the callable allocation alive for the full host observation.
    let entry = unsafe { std::mem::transmute::<*const u8, Entry>(module.get_finalized_function(id)) };
    let frame = if registration == "registered" {
        Some(RegisteredFrame::new(unwind_info.ok_or("missing unwind information")?, module.isa(), entry)?)
    } else {
        None
    };
    let host_result = unsafe { host_call(entry, code_size) };
    drop(frame);
    println!("after {}", unsafe { callback_fde_registered() });
    // There are no remaining callers or registered frame tables for this allocation.
    unsafe { module.free_memory() };
    if host_result != 0 {
        return Err("host observation failed".into());
    }
    Ok(())
}

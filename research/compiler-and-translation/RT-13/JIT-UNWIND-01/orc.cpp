#include "observer.h"

#include <llvm/AsmParser/Parser.h>
#include <llvm/ExecutionEngine/Orc/LLJIT.h>
#include <llvm/ExecutionEngine/Orc/ObjectTransformLayer.h>
#include <llvm/IR/Verifier.h>
#include <llvm/Object/ELFObjectFile.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/TargetSelect.h>
#include <llvm/Support/raw_ostream.h>

int main(int argc, char **argv) {
    if (argc != 3 || llvm::InitializeNativeTarget() || llvm::InitializeNativeTargetAsmPrinter())
        return 1;
    llvm::ExitOnError checked;
    llvm::orc::JITTargetMachineBuilder target(llvm::Triple("x86_64-unknown-linux-gnu"));
    target.setCPU("x86-64");
    target.setCodeGenOptLevel(llvm::CodeGenOptLevel::None);
    auto jit = checked(llvm::orc::LLJITBuilder().setJITTargetMachineBuilder(std::move(target)).create());
    size_t size = 0;
    jit->getObjTransformLayer().setTransform(
        [&](std::unique_ptr<llvm::MemoryBuffer> buffer)
            -> llvm::Expected<std::unique_ptr<llvm::MemoryBuffer>> {
            auto object = checked(llvm::object::ObjectFile::createELFObjectFile(buffer->getMemBufferRef()));
            for (const auto &symbol : object->symbols()) {
                if (checked(symbol.getName()) == "jit_step")
                    size = llvm::object::ELFSymbolRef(symbol).getSize();
            }
            std::error_code error;
            llvm::raw_fd_ostream file(argv[2], error);
            if (error)
                return llvm::errorCodeToError(error);
            file << buffer->getBuffer();
            file.close();
            return buffer;
        });
    auto context = std::make_unique<llvm::LLVMContext>();
    llvm::SMDiagnostic diagnostic;
    auto module = llvm::parseAssemblyFile(argv[1], diagnostic, *context);
    if (!module) {
        diagnostic.print(argv[0], llvm::errs());
        return 1;
    }
    module->setDataLayout(jit->getDataLayout());
    if (llvm::verifyModule(*module, &llvm::errs()))
        return 1;
    checked(jit->addIRModule(llvm::orc::ThreadSafeModule(std::move(module), std::move(context))));
    auto entry = checked(jit->lookup("jit_step")).toPtr<jit_entry>();
    return size ? host_call(entry, size) : 1;
}

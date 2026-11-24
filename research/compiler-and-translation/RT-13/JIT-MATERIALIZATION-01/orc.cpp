#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <string>
#include <vector>

#include <llvm/AsmParser/Parser.h>
#include <llvm/ExecutionEngine/Orc/LLJIT.h>
#include <llvm/IR/Verifier.h>
#include <llvm/Passes/PassBuilder.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/TargetSelect.h>

namespace {
using Entry = uint32_t (*)(uint32_t, uint32_t, uint32_t, void (*)(uint32_t), uint32_t *);
std::vector<uint32_t> Events;

extern "C" void collect(uint32_t value) {
    Events.push_back(value);
}

void verify(llvm::Module &module) {
    if (llvm::verifyModule(module, &llvm::errs()))
        std::exit(1);
}

void optimize(llvm::Module &module, llvm::OptimizationLevel level) {
    llvm::LoopAnalysisManager loops;
    llvm::FunctionAnalysisManager functions;
    llvm::CGSCCAnalysisManager sccs;
    llvm::ModuleAnalysisManager modules;
    llvm::PassBuilder builder;
    builder.registerModuleAnalyses(modules);
    builder.registerCGSCCAnalyses(sccs);
    builder.registerFunctionAnalyses(functions);
    builder.registerLoopAnalyses(loops);
    builder.crossRegisterProxies(loops, functions, sccs, modules);
    auto passes = level == llvm::OptimizationLevel::O0
        ? builder.buildO0DefaultPipeline(level)
        : builder.buildPerModuleDefaultPipeline(level);
    passes.run(module, modules);
}
}

int main(int argc, char **argv) {
    if ((argc != 4 && argc != 5) || (std::string(argv[1]) != "0" && std::string(argv[1]) != "3")) {
        std::cerr << "usage: latency-orc 0|3 samples input.ll [checks.txt]\n";
        return 1;
    }
    std::ifstream input(argv[3]);
    if (!input) return 1;
    const std::string ir{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
    std::vector<std::array<uint32_t, 3>> cases{{3, 1, 1}, {0x7fffffff, 1, 1}, {7, 5, 0}, {4, 3, 2}};
    if (argc == 5) {
        std::ifstream vectors(argv[4]);
        if (!vectors) return 1;
        cases.clear();
        uint32_t a, b, enabled;
        while (vectors >> a) {
            if (!(vectors >> b >> enabled)) return 1;
            cases.push_back({a, b, enabled});
        }
        if (!vectors.eof() || cases.empty()) return 1;
    }
    bool speed = std::string(argv[1]) == "3";
    if (llvm::InitializeNativeTarget() || llvm::InitializeNativeTargetAsmPrinter()) return 1;
    llvm::ExitOnError checked;
    for (int index = 0; index < std::stoi(argv[2]); ++index) {
        const auto start = std::chrono::steady_clock::now();
        llvm::orc::JITTargetMachineBuilder target(llvm::Triple("x86_64-unknown-linux-gnu"));
        target.setCPU("x86-64");
        target.setCodeGenOptLevel(speed ? llvm::CodeGenOptLevel::Aggressive : llvm::CodeGenOptLevel::None);
        auto jit = checked(llvm::orc::LLJITBuilder().setJITTargetMachineBuilder(std::move(target)).create());
        auto context = std::make_unique<llvm::LLVMContext>();
        llvm::SMDiagnostic diagnostic;
        auto module = llvm::parseAssembly(llvm::MemoryBufferRef(ir, "fixture"), diagnostic, *context);
        if (!module) {
            diagnostic.print(argv[0], llvm::errs());
            return 1;
        }
        module->setDataLayout(jit->getDataLayout());
        verify(*module);
        optimize(*module, speed ? llvm::OptimizationLevel::O3 : llvm::OptimizationLevel::O0);
        verify(*module);
        checked(jit->addIRModule(llvm::orc::ThreadSafeModule(std::move(module), std::move(context))));
        auto entry = checked(jit->lookup("probe_0")).toPtr<Entry>();
        const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count();
        std::cout << "time " << index << ' ' << elapsed << '\n';
        for (const auto &test : cases) {
            uint32_t output = 0xabad1234;
            auto status = entry(test[0], test[1], test[2], collect, &output);
            std::cout << "check " << status << ' ' << output;
            for (auto event : Events) std::cout << ' ' << event;
            std::cout << '\n';
            Events.clear();
        }
    }
}

/* Use the target Android LLVM library so its backported module flags retain
 * their exact semantics. Verify the IR both before and after debug removal. */
#include <stdio.h>
#include <llvm-c/Analysis.h>
#include <llvm-c/BitReader.h>
#include <llvm-c/BitWriter.h>
#include <llvm-c/Core.h>
#include <llvm-c/DebugInfo.h>

int main(int argc, char **argv)
{
    LLVMContextRef context = LLVMContextCreate();
    LLVMMemoryBufferRef buffer = NULL;
    LLVMModuleRef module = NULL;
    char *message = NULL;
    int result = 1;
    if (argc != 3) { fputs("usage: strip_llvm_debug input output\n", stderr); goto done; }
    if (LLVMCreateMemoryBufferWithContentsOfFile(argv[1], &buffer, &message)) {
        fprintf(stderr, "%s\n", message); goto done;
    }
    if (LLVMParseBitcodeInContext2(context, buffer, &module)) goto done;
    if (LLVMVerifyModule(module, LLVMReturnStatusAction, &message)) {
        fprintf(stderr, "Input IR failed verification: %s\n", message); goto done;
    }
    LLVMDisposeMessage(message); message = NULL;
    LLVMStripModuleDebugInfo(module);
    if (LLVMVerifyModule(module, LLVMReturnStatusAction, &message)) {
        fprintf(stderr, "Output IR failed verification: %s\n", message); goto done;
    }
    if (LLVMWriteBitcodeToFile(module, argv[2])) goto done;
    result = 0;
done:
    LLVMDisposeMessage(message);
    if (module) LLVMDisposeModule(module);
    if (buffer) LLVMDisposeMemoryBuffer(buffer);
    LLVMContextDispose(context);
    return result;
}

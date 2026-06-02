/**
 * @file os_stubs.cpp
 * @brief Stub implementations for N64 OS functions not provided by librecomp.
 *
 * These functions are referenced by recompiled code but don't have
 * implementations in the N64ModernRuntime librecomp library. We provide
 * no-op stubs so the executable links. Real implementations can be added
 * as they become necessary for correct behavior.
 */

#include <cstdint>
#include <cstdio>

// Forward-declare recomp types to avoid pulling in the full header chain.
struct recomp_context;

// ---------------------------------------------------------------------------
// RSP audio microcode stub
// ---------------------------------------------------------------------------

enum class RspExitReason {
    Invalid,
    Broke,
    Yielded,
};

extern "C" RspExitReason n64_aspMain(uint8_t* rdram, uint32_t ucode_addr) {
    // TODO: Implement HLE audio RSP microcode processing.
    // For now, return Broke to signal task completion.
    (void)rdram;
    (void)ucode_addr;
    return RspExitReason::Broke;
}

// ---------------------------------------------------------------------------
// Controller Pak / PFS stubs  (recomp calling convention)
// ---------------------------------------------------------------------------

extern "C" void __osPfsSelectBank_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Controller Pak bank select — return 0 (success) in v0.
    (void)rdram;
    (void)ctx;
}

extern "C" void __osContRamWrite_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Controller RAM write.
    (void)rdram;
    (void)ctx;
}

extern "C" void __osContRamRead_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Controller RAM read.
    (void)rdram;
    (void)ctx;
}

extern "C" void osPfsIsPlug_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Check if Controller Pak is plugged in.
    // Return 0 (no pak) by leaving v0 at default.
    (void)rdram;
    (void)ctx;
}

extern "C" void osPfsInit_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Initialize Controller Pak filesystem.
    (void)rdram;
    (void)ctx;
}

// ---------------------------------------------------------------------------
// Debug / diagnostic stubs
// ---------------------------------------------------------------------------

extern "C" void send_packet_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Debug packet send (used by osWritebackDCache / rmon).
    (void)rdram;
    (void)ctx;
}

extern "C" void __osGetCause_recomp(uint8_t* rdram, recomp_context* ctx) {
    // Stub: Get MIPS cause register — return 0.
    (void)rdram;
    (void)ctx;
}

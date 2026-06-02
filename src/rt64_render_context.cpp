/**
 * @file rt64_render_context.cpp
 * @brief RT64 RendererContext implementation for WaveRace64-Recomp.
 *
 * Wraps the RT64::Application into an ultramodern::renderer::RendererContext
 * subclass so that the N64ModernRuntime can drive display list submission,
 * screen updates, and shutdown through a uniform interface.
 */

#include "rt64_render_context.h"

#include <cstdio>
#include <cassert>

#include "ultramodern/renderer_context.hpp"
#include "ultramodern/config.hpp"

#include "hle/rt64_application.h"

// ---------------------------------------------------------------------------
// RT64 RendererContext subclass
// ---------------------------------------------------------------------------

namespace wr64 {

class RT64Context : public ultramodern::renderer::RendererContext {
public:
    RT64Context(uint8_t* rdram, ultramodern::renderer::WindowHandle window_handle, bool developer_mode) {
        // Populate the RT64 core struct from the emulated hardware state.
        RT64::Application::Core core{};

        // The RDRAM pointer is the base of the emulated N64 memory.
        core.RDRAM = rdram;

        // N64 ROM header sits at the start of RDRAM in the recompiler's memory layout.
        // The header is the first 0x40 bytes of the ROM, copied to RDRAM by the IPL.
        core.HEADER = rdram;

        // DMEM and IMEM are at fixed offsets within the SP memory space.
        // In the recompiler, these are at 0x04000000 and 0x04001000 respectively,
        // mapped relative to RDRAM with a fixed offset.
        // For now, set to nullptr — RT64 doesn't use them for HLE rendering.
        core.DMEM = nullptr;
        core.IMEM = nullptr;

        // VI register pointers: RT64 reads these from RDRAM to determine framebuffer.
        // The ultramodern runtime sets up VI registers at known addresses.
        // We obtain the VI registers from the ultramodern runtime.
        auto* vi_regs = ultramodern::renderer::get_vi_regs();
        core.VI_STATUS_REG          = &vi_regs->VI_STATUS_REG;
        core.VI_ORIGIN_REG          = &vi_regs->VI_ORIGIN_REG;
        core.VI_WIDTH_REG           = &vi_regs->VI_WIDTH_REG;
        core.VI_INTR_REG            = &vi_regs->VI_INTR_REG;
        core.VI_V_CURRENT_LINE_REG  = &vi_regs->VI_V_CURRENT_LINE_REG;
        core.VI_TIMING_REG          = &vi_regs->VI_TIMING_REG;
        core.VI_V_SYNC_REG          = &vi_regs->VI_V_SYNC_REG;
        core.VI_H_SYNC_REG          = &vi_regs->VI_H_SYNC_REG;
        core.VI_LEAP_REG            = &vi_regs->VI_LEAP_REG;
        core.VI_H_START_REG         = &vi_regs->VI_H_START_REG;
        core.VI_V_START_REG         = &vi_regs->VI_V_START_REG;
        core.VI_V_BURST_REG         = &vi_regs->VI_V_BURST_REG;
        core.VI_X_SCALE_REG         = &vi_regs->VI_X_SCALE_REG;
        core.VI_Y_SCALE_REG         = &vi_regs->VI_Y_SCALE_REG;

        // DPC registers — not strictly needed for basic HLE, but RT64 references them.
        // Set to nullptr for now; advanced RDP integration would fill these in.
        core.DPC_START_REG   = nullptr;
        core.DPC_END_REG     = nullptr;
        core.DPC_CURRENT_REG = nullptr;
        core.DPC_STATUS_REG  = nullptr;
        core.DPC_CLOCK_REG   = nullptr;
        core.DPC_BUFBUSY_REG = nullptr;
        core.DPC_PIPEBUSY_REG = nullptr;
        core.DPC_TMEM_REG    = nullptr;
        core.MI_INTR_REG     = nullptr;
        core.checkInterrupts = nullptr;

        // Set up the SDL window for RT64.
#if defined(__linux__) || defined(__ANDROID__)
        core.window = RT64::RenderWindow(window_handle);
#elif defined(_WIN32)
        core.window = RT64::RenderWindow(window_handle.window);
#elif defined(__APPLE__)
        core.window = RT64::RenderWindow(window_handle.window, window_handle.view);
#endif

        // Configure the RT64 application.
        RT64::ApplicationConfiguration app_config{};
        app_config.appId = "waverace64";

        // Create the RT64 application.
        app_ = std::make_unique<RT64::Application>(core, app_config);

        // Attempt setup.
        auto result = app_->setup(0);

        switch (result) {
            case RT64::Application::SetupResult::Success:
                setup_result = ultramodern::renderer::SetupResult::Success;
                break;
            case RT64::Application::SetupResult::DynamicLibrariesNotFound:
                setup_result = ultramodern::renderer::SetupResult::DynamicLibrariesNotFound;
                break;
            case RT64::Application::SetupResult::InvalidGraphicsAPI:
                setup_result = ultramodern::renderer::SetupResult::InvalidGraphicsAPI;
                break;
            case RT64::Application::SetupResult::GraphicsAPINotFound:
                setup_result = ultramodern::renderer::SetupResult::GraphicsAPINotFound;
                break;
            case RT64::Application::SetupResult::GraphicsDeviceNotFound:
                setup_result = ultramodern::renderer::SetupResult::GraphicsDeviceNotFound;
                break;
        }

        // Set the chosen graphics API.
        // RT64 uses its own GraphicsAPI enum — map to ultramodern's.
        // Default to Vulkan on Linux.
        chosen_api = ultramodern::renderer::GraphicsApi::Vulkan;

        printf("[WR64-RT64] Renderer context created (result=%d)\n", static_cast<int>(result));
    }

    ~RT64Context() override {
        if (app_) {
            app_->end();
        }
    }

    bool valid() override {
        return setup_result == ultramodern::renderer::SetupResult::Success && app_ != nullptr;
    }

    bool update_config(const ultramodern::renderer::GraphicsConfig& old_config,
                       const ultramodern::renderer::GraphicsConfig& new_config) override {
        // TODO: Map GraphicsConfig fields to RT64's UserConfiguration and apply changes.
        (void)old_config;
        (void)new_config;
        return true;
    }

    void enable_instant_present() override {
        // TODO: Configure RT64 for instant present mode (reduces latency).
    }

    void send_dl(const OSTask* task) override {
        if (!app_) return;

        // Extract display list start and end addresses from the OSTask.
        uint32_t dl_start = task->t.data_ptr;
        uint32_t dl_end   = task->t.data_ptr + task->t.data_size;

        app_->processDisplayLists(
            const_cast<uint8_t*>(app_->core.RDRAM),
            dl_start,
            dl_end,
            true  // HLE mode
        );
    }

    void update_screen() override {
        if (app_) {
            app_->updateScreen();
        }
    }

    void shutdown() override {
        if (app_) {
            app_->end();
            app_.reset();
        }
    }

    uint32_t get_display_framerate() const override {
        // Wave Race 64 targets 30fps (NTSC).
        // TODO: Query actual display refresh rate from RT64.
        return 30;
    }

    float get_resolution_scale() const override {
        // TODO: Return configurable resolution scale from RT64.
        return 1.0f;
    }

private:
    std::unique_ptr<RT64::Application> app_;
};

// ---------------------------------------------------------------------------
// Factory function
// ---------------------------------------------------------------------------

std::unique_ptr<ultramodern::renderer::RendererContext> create_render_context(
    uint8_t* rdram,
    ultramodern::renderer::WindowHandle window_handle,
    bool developer_mode
) {
    auto ctx = std::make_unique<RT64Context>(rdram, window_handle, developer_mode);
    if (!ctx->valid()) {
        fprintf(stderr, "[WR64-RT64] Failed to create render context (result=%d)\n",
                static_cast<int>(ctx->get_setup_result()));
        return nullptr;
    }
    return ctx;
}

} // namespace wr64

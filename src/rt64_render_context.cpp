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
// Static dummy buffers required by RT64 (must persist for the lifetime of app)
// ---------------------------------------------------------------------------

// ROM header placeholder — RT64 reads the first 0x40 bytes for cartridge info.
// We don't need real header data for HLE rendering.
static uint8_t s_dummy_rom_header[0x40] = {};

// SP DMEM/IMEM — RT64's RSP HLE doesn't use these but the core struct must be
// non-null to avoid null-dereferences inside RT64's state setup paths.
static uint8_t s_DMEM[0x1000] = {};
static uint8_t s_IMEM[0x1000] = {};

// RDP / MI register storage — RT64 may read/write these during HLE rendering.
// Providing real zero-initialised storage prevents nullptr dereferences.
static unsigned int s_MI_INTR_REG     = 0;
static unsigned int s_DPC_START_REG   = 0;
static unsigned int s_DPC_END_REG     = 0;
static unsigned int s_DPC_CURRENT_REG = 0;
static unsigned int s_DPC_STATUS_REG  = 0;
static unsigned int s_DPC_CLOCK_REG   = 0;
static unsigned int s_DPC_BUFBUSY_REG = 0;
static unsigned int s_DPC_PIPEBUSY_REG= 0;
static unsigned int s_DPC_TMEM_REG    = 0;

// No-op interrupt check — the recompiler runtime handles interrupts itself.
static void dummy_check_interrupts() {}

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

        // Use the static dummy header — real ROM header bytes are not needed for HLE.
        core.HEADER = s_dummy_rom_header;

        // DMEM/IMEM must be non-null; RT64 may reference them during state init.
        core.DMEM = s_DMEM;
        core.IMEM = s_IMEM;

        // Wire up a no-op interrupt callback. The ultramodern runtime owns
        // interrupt delivery; RT64 does not need to trigger them directly.
        core.checkInterrupts = dummy_check_interrupts;

        // RDP / MI registers — provide real storage so RT64 can read/write safely.
        core.MI_INTR_REG      = &s_MI_INTR_REG;
        core.DPC_START_REG    = &s_DPC_START_REG;
        core.DPC_END_REG      = &s_DPC_END_REG;
        core.DPC_CURRENT_REG  = &s_DPC_CURRENT_REG;
        core.DPC_STATUS_REG   = &s_DPC_STATUS_REG;
        core.DPC_CLOCK_REG    = &s_DPC_CLOCK_REG;
        core.DPC_BUFBUSY_REG  = &s_DPC_BUFBUSY_REG;
        core.DPC_PIPEBUSY_REG = &s_DPC_PIPEBUSY_REG;
        core.DPC_TMEM_REG     = &s_DPC_TMEM_REG;

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

        // Set up the SDL window for RT64.
#if defined(_WIN32)
        core.window = window_handle.window;
#elif defined(__APPLE__)
        core.window.window = window_handle.window;
        core.window.view   = window_handle.view;
#else
        // Linux / Android: WindowHandle IS SDL_Window*
        core.window = window_handle;
#endif

        // Configure the RT64 application.
        RT64::ApplicationConfiguration app_config{};
        app_config.appId = "waverace64";
        // Disable config file I/O — we manage settings ourselves.
        app_config.useConfigurationFile = false;

        // Create the RT64 application.
        app_ = std::make_unique<RT64::Application>(core, app_config);

        // Enable developer/debug mode if requested.
        app_->userConfig.developerMode = developer_mode;

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

        if (result != RT64::Application::SetupResult::Success) {
            app_.reset();
            return;
        }

        // Map the API that RT64 actually chose.
        switch (app_->chosenGraphicsAPI) {
            case RT64::UserConfiguration::GraphicsAPI::D3D12:
                chosen_api = ultramodern::renderer::GraphicsApi::D3D12;
                break;
            case RT64::UserConfiguration::GraphicsAPI::Vulkan:
                chosen_api = ultramodern::renderer::GraphicsApi::Vulkan;
                break;
            case RT64::UserConfiguration::GraphicsAPI::Metal:
                chosen_api = ultramodern::renderer::GraphicsApi::Metal;
                break;
            default:
                chosen_api = ultramodern::renderer::GraphicsApi::Vulkan;
                break;
        }

        printf("[WR64-RT64] Renderer context created (result=%d, api=%d)\n",
               static_cast<int>(result), static_cast<int>(chosen_api));
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
        if (!app_) return;
        // Enable present-early mode for minimal latency (matches reference).
        app_->enhancementConfig.presentation.mode =
            RT64::EnhancementConfiguration::Presentation::Mode::PresentEarly;
        app_->updateEnhancementConfig();
    }

    void send_dl(const OSTask* task) override {
        if (!app_) return;

        // task->t.ucode / ucode_data / data_ptr are PTR(u64) = int32_t holding
        // N64 KSEG0 virtual addresses (e.g. 0x80XXXXXX).
        // RT64 expects physical byte offsets into the RDRAM buffer.
        // Masking with 0x3FFFFFF strips the KSEG0/KSEG1 high bits and gives
        // the physical address within the N64's 64MB address space.
        uint32_t ucode_phys      = static_cast<uint32_t>(task->t.ucode)      & 0x3FFFFFFu;
        uint32_t ucode_data_phys = static_cast<uint32_t>(task->t.ucode_data) & 0x3FFFFFFu;
        uint32_t dl_start_phys   = static_cast<uint32_t>(task->t.data_ptr)   & 0x3FFFFFFu;

        fprintf(stderr, "[WR64-RT64] send_dl: ucode=0x%07X ucode_data=0x%07X data_ptr=0x%07X\n",
                ucode_phys, ucode_data_phys, dl_start_phys);

        // Reset the RSP state machine before processing each new display list.
        // This prevents prior-frame geometry or matrix state from leaking.
        app_->state->rsp->reset();

        // Tell the HLE interpreter which GBI microcode variant to use.
        // This must be called before processDisplayLists() or hleGBI will be null.
        app_->interpreter->loadUCodeGBI(ucode_phys, ucode_data_phys, true);

        // Process the display list. Pass 0 for dlEndAddress — RT64 will walk
        // the list until it encounters a G_ENDDL command.
        app_->processDisplayLists(
            app_->core.RDRAM,
            dl_start_phys,
            0,    // end address: 0 means walk until G_ENDDL
            true  // HLE mode
        );

        fprintf(stderr, "[WR64-RT64] send_dl: DONE\n");
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
        if (app_ && app_->presentQueue) {
            return app_->presentQueue->ext.sharedResources->swapChainRate;
        }
        // Wave Race 64 targets 30fps (NTSC) — use as fallback.
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

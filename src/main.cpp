/**
 * @file main.cpp
 * @brief WaveRace64-Recomp game integration entry point.
 *
 * Registers the Wave Race 64 GameEntry with the N64ModernRuntime,
 * builds the overlay section table, wires up all callbacks, and
 * calls recomp::start() to launch the game.
 */

#include <cstdio>
#include <cstdint>
#include <string>

#include "librecomp/game.hpp"
#include "librecomp/overlays.hpp"
#include "librecomp/sections.h"
#include "librecomp/addresses.hpp"

// Game-specific headers
#include "rt64_render_context.h"
#include "rsp_microcode.h"
#include "audio.h"
#include "input.h"

// Pull in the recompiled function declarations and overlay tables.
#include "recomp_overlays.inl"

// Forward-declare the recomp entrypoint (defined in RecompiledFuncs/funcs.h,
// already included transitively through recomp_overlays.inl -> funcs.h).

// ---------------------------------------------------------------------------
// Wave Race 64 (USA Rev 1) constants
// ---------------------------------------------------------------------------
static constexpr uint64_t WR64_ROM_HASH          = 0x2B675E2250A604FCull;
static constexpr gpr      WR64_ENTRYPOINT_ADDR   = (gpr)(int32_t)0x80046800u;
static constexpr const char* WR64_INTERNAL_NAME  = "WAVE RACE 64";
// Game uses 4-Kbit EEPROM for saves.

// ---------------------------------------------------------------------------
// Section table
// ---------------------------------------------------------------------------
// Section data extracted from waverace64.us.rev1.syms.toml.
// The FuncEntry arrays are defined in recomp_overlays.inl.
//
// 19 code sections (indices 0-18):
//   0  .main            rom=0x00001000  vram=0x80046800  size=0xA85D0
//   1  .codeseg         rom=0x000A95D0  vram=0x801DAFA0  size=0x4CAC0
//   2  .segment_1B1FB0  rom=0x001B1FB0  vram=0x802C5800  size=0x1F10
//   3  .ovl_i0          rom=0x001B3EC0  vram=0x802C5800  size=0x16E0
//   4  .ovl_i1          rom=0x001B55A0  vram=0x802C5800  size=0x3EA0
//   5  .ovl_i2          rom=0x001B9440  vram=0x802C5800  size=0x3450
//   6  .ovl_i3          rom=0x001BC890  vram=0x802C5800  size=0x1820
//   7  .ovl_i4          rom=0x001BE0B0  vram=0x802C5800  size=0x1EA0
//   8  .ovl_i5          rom=0x001BFF50  vram=0x802C5800  size=0x2300
//   9  .ovl_i6          rom=0x001C2250  vram=0x802C5800  size=0x1530
//  10  .seg_1C3780      rom=0x001C3780  vram=0x802C5800  size=0x580
//  11  .seg_1C3D00      rom=0x001C3D00  vram=0x802C5800  size=0x6F0
//  12  .ovl_i7          rom=0x001C43F0  vram=0x802C5800  size=0x5B0
//  13  .ovl_i8          rom=0x001C49A0  vram=0x802C5800  size=0x1D30
//  14  .ovl_i9          rom=0x001C66D0  vram=0x802C5800  size=0x2A80
//  15  .ovl_i10         rom=0x001C9150  vram=0x802C5800  size=0x1330
//  16  .ovl_i11         rom=0x001CA480  vram=0x802C5800  size=0x9C0
//  17  .ovl_i12         rom=0x001CAE40  vram=0x802C5800  size=0xCB0
//  18  .ovl_i13         rom=0x001CBAF0  vram=0x802C5800  size=0x3690

static SectionTableEntry code_sections[] = {
    { .rom_addr = 0x00001000, .ram_addr = 0x80046800, .size = 0xA85D0,
      .funcs = section_0_main_funcs, .num_funcs = ARRLEN(section_0_main_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 0 },
    { .rom_addr = 0x000A95D0, .ram_addr = 0x801DAFA0, .size = 0x4CAC0,
      .funcs = section_1_codeseg_funcs, .num_funcs = ARRLEN(section_1_codeseg_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 1 },
    { .rom_addr = 0x001B1FB0, .ram_addr = 0x802C5800, .size = 0x1F10,
      .funcs = section_2_segment_1B1FB0_funcs, .num_funcs = ARRLEN(section_2_segment_1B1FB0_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 2 },
    { .rom_addr = 0x001B3EC0, .ram_addr = 0x802C5800, .size = 0x16E0,
      .funcs = section_3_ovl_i0_funcs, .num_funcs = ARRLEN(section_3_ovl_i0_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 3 },
    { .rom_addr = 0x001B55A0, .ram_addr = 0x802C5800, .size = 0x3EA0,
      .funcs = section_4_ovl_i1_funcs, .num_funcs = ARRLEN(section_4_ovl_i1_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 4 },
    { .rom_addr = 0x001B9440, .ram_addr = 0x802C5800, .size = 0x3450,
      .funcs = section_5_ovl_i2_funcs, .num_funcs = ARRLEN(section_5_ovl_i2_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 5 },
    { .rom_addr = 0x001BC890, .ram_addr = 0x802C5800, .size = 0x1820,
      .funcs = section_6_ovl_i3_funcs, .num_funcs = ARRLEN(section_6_ovl_i3_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 6 },
    { .rom_addr = 0x001BE0B0, .ram_addr = 0x802C5800, .size = 0x1EA0,
      .funcs = section_7_ovl_i4_funcs, .num_funcs = ARRLEN(section_7_ovl_i4_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 7 },
    { .rom_addr = 0x001BFF50, .ram_addr = 0x802C5800, .size = 0x2300,
      .funcs = section_8_ovl_i5_funcs, .num_funcs = ARRLEN(section_8_ovl_i5_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 8 },
    { .rom_addr = 0x001C2250, .ram_addr = 0x802C5800, .size = 0x1530,
      .funcs = section_9_ovl_i6_funcs, .num_funcs = ARRLEN(section_9_ovl_i6_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 9 },
    { .rom_addr = 0x001C3780, .ram_addr = 0x802C5800, .size = 0x580,
      .funcs = section_10_seg_1C3780_funcs, .num_funcs = ARRLEN(section_10_seg_1C3780_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 10 },
    { .rom_addr = 0x001C3D00, .ram_addr = 0x802C5800, .size = 0x6F0,
      .funcs = section_11_seg_1C3D00_funcs, .num_funcs = ARRLEN(section_11_seg_1C3D00_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 11 },
    { .rom_addr = 0x001C43F0, .ram_addr = 0x802C5800, .size = 0x5B0,
      .funcs = section_12_ovl_i7_funcs, .num_funcs = ARRLEN(section_12_ovl_i7_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 12 },
    { .rom_addr = 0x001C49A0, .ram_addr = 0x802C5800, .size = 0x1D30,
      .funcs = section_13_ovl_i8_funcs, .num_funcs = ARRLEN(section_13_ovl_i8_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 13 },
    { .rom_addr = 0x001C66D0, .ram_addr = 0x802C5800, .size = 0x2A80,
      .funcs = section_14_ovl_i9_funcs, .num_funcs = ARRLEN(section_14_ovl_i9_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 14 },
    { .rom_addr = 0x001C9150, .ram_addr = 0x802C5800, .size = 0x1330,
      .funcs = section_15_ovl_i10_funcs, .num_funcs = ARRLEN(section_15_ovl_i10_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 15 },
    { .rom_addr = 0x001CA480, .ram_addr = 0x802C5800, .size = 0x9C0,
      .funcs = section_16_ovl_i11_funcs, .num_funcs = ARRLEN(section_16_ovl_i11_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 16 },
    { .rom_addr = 0x001CAE40, .ram_addr = 0x802C5800, .size = 0xCB0,
      .funcs = section_17_ovl_i12_funcs, .num_funcs = ARRLEN(section_17_ovl_i12_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 17 },
    { .rom_addr = 0x001CBAF0, .ram_addr = 0x802C5800, .size = 0x3690,
      .funcs = section_18_ovl_i13_funcs, .num_funcs = ARRLEN(section_18_ovl_i13_funcs),
      .relocs = nullptr, .num_relocs = 0, .index = 18 },
};

static constexpr size_t NUM_CODE_SECTIONS  = ARRLEN(code_sections);
// Total sections including potential data/BSS sections referenced by relocs.
// For now, equals code section count since we have no relocation data.
static constexpr size_t TOTAL_NUM_SECTIONS = 21; // 19 code + potential data/BSS sections

// ---------------------------------------------------------------------------
// SDL2 window / gfx callbacks
// ---------------------------------------------------------------------------
#include <SDL2/SDL.h>

static SDL_Window* sdl_window = nullptr;

static void* create_gfx() {
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) {
        fprintf(stderr, "[WR64] SDL_Init failed: %s\n", SDL_GetError());
        return nullptr;
    }
    return nullptr; // gfx_data not used
}

static ultramodern::renderer::WindowHandle create_window(void* /*gfx_data*/) {
    sdl_window = SDL_CreateWindow(
        "Wave Race 64",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        1280, 960,
        SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI
    );
    if (!sdl_window) {
        fprintf(stderr, "[WR64] SDL_CreateWindow failed: %s\n", SDL_GetError());
    }
    return sdl_window;
}

static void update_gfx(void* /*gfx_data*/) {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        switch (event.type) {
            case SDL_QUIT:
                ultramodern::quit();
                break;
            case SDL_KEYDOWN:
                if (event.key.keysym.scancode == SDL_SCANCODE_ESCAPE) {
                    ultramodern::quit();
                }
                break;
            default:
                break;
        }
    }
}

// ---------------------------------------------------------------------------
// Events callbacks
// ---------------------------------------------------------------------------
static void vi_callback() {
    // Called each VI interrupt. Can be used for frame pacing.
}

static void gfx_init_callback() {
    // Called when the graphics subsystem is initialized.
}

// ---------------------------------------------------------------------------
// Error handling callback
// ---------------------------------------------------------------------------
static void error_message_box(const char* msg) {
    fprintf(stderr, "[WR64] ERROR: %s\n", msg);
    if (sdl_window) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Wave Race 64 - Error", msg, sdl_window);
    }
}

// ---------------------------------------------------------------------------
// Threads callback
// ---------------------------------------------------------------------------
static std::string get_game_thread_name(int id) {
    switch (id) {
        case 1: return "WR64 Idle";
        case 3: return "WR64 Main";
        case 4: return "WR64 Audio";
        case 5: return "WR64 Sched";
        default: return "WR64 Thread " + std::to_string(id);
    }
}

// ---------------------------------------------------------------------------
// main()
// ---------------------------------------------------------------------------
int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    printf("[WR64] Wave Race 64 PC Recompilation v0.1.0\n");

    // -----------------------------------------------------------------------
    // 1. Register overlay sections
    // -----------------------------------------------------------------------
    recomp::overlays::overlay_section_table_data_t section_table {
        .code_sections    = code_sections,
        .num_code_sections = NUM_CODE_SECTIONS,
        .total_num_sections = TOTAL_NUM_SECTIONS,
    };

    // Overlay-by-index mapping (not needed if overlay loading uses ROM address matching).
    recomp::overlays::overlays_by_index_t overlays_by_index {
        .table = nullptr,
        .len   = 0,
    };

    recomp::overlays::register_overlays(section_table, overlays_by_index);

    // -----------------------------------------------------------------------
    // 2. Register the game entry
    // -----------------------------------------------------------------------
    recomp::GameEntry wr64_entry {
        .rom_hash            = WR64_ROM_HASH,
        .internal_name       = WR64_INTERNAL_NAME,
        .game_id             = u8"waverace64",
        .mod_game_id         = "waverace64",
        .save_type           = recomp::SaveType::Eep4k,
        .is_enabled          = true,
        .entrypoint_address  = WR64_ENTRYPOINT_ADDR,
        .entrypoint          = recomp_entrypoint,
    };

    if (!recomp::register_game(wr64_entry)) {
        fprintf(stderr, "[WR64] Failed to register game entry!\n");
        return 1;
    }
    printf("[WR64] Game registered: %s (hash 0x%016llX)\n",
           wr64_entry.internal_name.c_str(),
           (unsigned long long)wr64_entry.rom_hash);

    // -----------------------------------------------------------------------
    // 3. Build the Configuration and start
    // -----------------------------------------------------------------------
    recomp::Configuration config {
        .project_version = { .major = 0, .minor = 1, .patch = 0, .suffix = "-alpha" },

        .window_handle = ultramodern::renderer::WindowHandle{},

        .rsp_callbacks = {
            .get_rsp_microcode = wr64::get_rsp_microcode,
        },

        .renderer_callbacks = {
            .create_render_context = wr64::create_render_context,
        },

        .audio_callbacks = {
            .queue_samples       = wr64::audio_queue_samples,
            .get_frames_remaining = wr64::audio_get_frames_remaining,
            .set_frequency       = wr64::audio_set_frequency,
        },

        .input_callbacks = {
            .poll_input              = wr64::input_poll,
            .get_input               = wr64::input_get,
            .set_rumble              = wr64::input_set_rumble,
            .get_connected_device_info = wr64::input_get_connected_device_info,
        },

        .gfx_callbacks = {
            .create_gfx    = create_gfx,
            .create_window = create_window,
            .update_gfx    = update_gfx,
        },

        .events_callbacks = {
            .vi_callback       = vi_callback,
            .gfx_init_callback = gfx_init_callback,
        },

        .error_handling_callbacks = {
            .message_box = error_message_box,
        },

        .threads_callbacks = {
            .get_game_thread_name = get_game_thread_name,
        },

        .message_queue_control = {
            // Wave Race 64 defaults: requeue timer, sp, si, dp; don't requeue ai, vi, pi.
        },
    };

    printf("[WR64] Starting recomp runtime...\n");
    recomp::start(config);

    // Cleanup
    if (sdl_window) {
        SDL_DestroyWindow(sdl_window);
        sdl_window = nullptr;
    }
    SDL_Quit();

    printf("[WR64] Exited cleanly.\n");
    return 0;
}

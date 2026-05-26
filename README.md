# WaveRace64-Recomp

A native PC port of **Wave Race 64** (USA Rev 1) using [N64Recomp](https://github.com/N64Recomp/N64Recomp) static recompilation.

> ⚠️ **Early Development** — This project is in its initial setup phase. Not yet playable.

## What is this?

This project uses static recompilation to translate Wave Race 64's N64 MIPS binary code into native PC code, enabling the game to run natively on modern hardware with enhancements like:

- Arbitrary resolution support (720p, 1080p, 4K+)
- Widescreen and ultrawide aspect ratios
- Modern controller support (Xbox, PlayStation, Switch Pro, keyboard+mouse)
- Enhanced rendering via [RT64](https://github.com/rt64/rt64)
- 60fps support (planned)

## Prerequisites

### Required
- **Wave Race 64 (USA Rev 1) ROM** — You must legally own and provide your own ROM file
  - Expected SHA-1: `508dfc2d4caa42b6f6de5263d0aed5e44ac7966a`
  - Place as `baserom.us.rev1.z64` in the project root
- **CMake** ≥ 3.20
- **C++ Compiler** — MSVC 2022 (Windows), GCC 12+ (Linux), or Clang 15+
- **Python** ≥ 3.10

### Platform-Specific
- **Windows:** Windows 10 SDK, Visual Studio 2022 with C++ workload
- **Linux:** Vulkan SDK ≥ 1.3, SDL2 development libraries

## Building

> Build instructions coming soon — project is in setup phase.

## Project Structure

```
WaveRace64-Recomp/
├── lib/                    # Git submodules
│   ├── N64Recomp/          # Static recompiler (MIPS → C)
│   ├── rt64/               # GPU rendering engine (F3D → D3D12/Vulkan)
│   └── N64ModernRuntime/   # Runtime library (OS stubs, threading, etc.)
├── src/                    # Game-specific source code
│   └── patches/            # Function patches and overrides
├── recomp/                 # N64Recomp configuration
│   └── waverace64.toml     # Recompiler configuration
├── assets/                 # Non-copyrighted application assets
├── docs/                   # Documentation
└── scripts/                # Build and utility scripts
```

## Related Projects

| Project | Description |
|---------|-------------|
| [N64Recomp](https://github.com/N64Recomp/N64Recomp) | The static recompilation tool |
| [RT64](https://github.com/rt64/rt64) | N64 rendering engine for PC |
| [N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime) | Runtime support library |
| [Wave-Race-64 Decomp](https://github.com/WACOMalt/Wave-Race-64) | Our decomp fork (symbol source) |
| [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp) | Reference implementation (Majora's Mask) |

## Legal

This project does **not** contain any Nintendo copyrighted code or assets. You must provide your own legally-obtained ROM file to use this software.

## License

GPLv3 — see [LICENSE](LICENSE) for details.

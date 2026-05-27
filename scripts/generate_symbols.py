#!/usr/bin/env python3
"""
Generate N64Recomp symbols TOML from Wave Race 64 decomp project.

Parses symbol address files and the splat YAML configuration from the decomp
project, then outputs a properly formatted symbols TOML file for N64Recomp.

Usage:
    python generate_symbols.py [--decomp PATH] [--output PATH]
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Section definitions derived from the splat YAML (waverace64.us.rev1.yaml)
# ---------------------------------------------------------------------------
# Main segment: ROM 0x1000, VRAM 0x80046800, text portion ends at ROM 0x8CAB0
# (before rspboot microcode). After text: microcode, data, rodata, bss.
# The BSS extends VRAM up to 0x801DAFA0 (where codeseg starts).
#
# Codeseg: ROM 0xA95D0, VRAM 0x801DAFA0, text ends at ROM 0xCAE70.

MAIN_SECTIONS = [
    {
        "name": ".main",
        "rom": 0x1000,
        "vram": 0x80046800,
        "size": 0xA95D0 - 0x1000,   # Full ROM extent including data/rodata
        "text_vram_end": 0x80046800 + (0x8CAB0 - 0x1000),  # End of code, start of microcode
        "is_overlay": False,
    },
    {
        "name": ".codeseg",
        "rom": 0xA95D0,
        "vram": 0x801DAFA0,
        "size": 0xF6090 - 0xA95D0,
        "text_vram_end": 0x801DAFA0 + (0xCAE70 - 0xA95D0),  # End of code, start of data
        "is_overlay": False,
    },
]

OVERLAY_SECTIONS = [
    {"name": ".segment_1B1FB0", "rom": 0x1B1FB0, "vram": 0x802C5800, "size": 0x1B3EC0 - 0x1B1FB0},
    {"name": ".ovl_i0",         "rom": 0x1B3EC0, "vram": 0x802C5800, "size": 0x1B55A0 - 0x1B3EC0},
    {"name": ".ovl_i1",         "rom": 0x1B55A0, "vram": 0x802C5800, "size": 0x1B9440 - 0x1B55A0},
    {"name": ".ovl_i2",         "rom": 0x1B9440, "vram": 0x802C5800, "size": 0x1BC890 - 0x1B9440},
    {"name": ".ovl_i3",         "rom": 0x1BC890, "vram": 0x802C5800, "size": 0x1BE0B0 - 0x1BC890},
    {"name": ".ovl_i4",         "rom": 0x1BE0B0, "vram": 0x802C5800, "size": 0x1BFF50 - 0x1BE0B0},
    {"name": ".ovl_i5",         "rom": 0x1BFF50, "vram": 0x802C5800, "size": 0x1C2250 - 0x1BFF50},
    {"name": ".ovl_i6",         "rom": 0x1C2250, "vram": 0x802C5800, "size": 0x1C3780 - 0x1C2250},
    {"name": ".seg_1C3780",     "rom": 0x1C3780, "vram": 0x802C5800, "size": 0x1C3D00 - 0x1C3780},
    {"name": ".seg_1C3D00",     "rom": 0x1C3D00, "vram": 0x802C5800, "size": 0x1C43F0 - 0x1C3D00},
    {"name": ".ovl_i7",         "rom": 0x1C43F0, "vram": 0x802C5800, "size": 0x1C49A0 - 0x1C43F0},
    {"name": ".ovl_i8",         "rom": 0x1C49A0, "vram": 0x802C5800, "size": 0x1C66D0 - 0x1C49A0},
    {"name": ".ovl_i9",         "rom": 0x1C66D0, "vram": 0x802C5800, "size": 0x1C9150 - 0x1C66D0},
    {"name": ".ovl_i10",        "rom": 0x1C9150, "vram": 0x802C5800, "size": 0x1CA480 - 0x1C9150},
    {"name": ".ovl_i11",        "rom": 0x1CA480, "vram": 0x802C5800, "size": 0x1CAE40 - 0x1CA480},
    {"name": ".ovl_i12",        "rom": 0x1CAE40, "vram": 0x802C5800, "size": 0x1CBAF0 - 0x1CAE40},
    {"name": ".ovl_i13",        "rom": 0x1CBAF0, "vram": 0x802C5800, "size": 0x1CF180 - 0x1CBAF0},
    {"name": ".ovl_i14",        "rom": 0x1CF180, "vram": 0x802C5800, "size": 0x1CFB60 - 0x1CF180},
    {"name": ".ovl_i15",        "rom": 0x1CFB60, "vram": 0x802C5800, "size": 0x1D11D0 - 0x1CFB60},
]

# Text portion end VRAM for overlay sections (first data subsegment ROM offset
# converted to VRAM offset from section start). Derived from splat YAML.
OVERLAY_TEXT_ROM_ENDS = {
    ".segment_1B1FB0": 0x1B3E10,
    ".ovl_i0":         0x1B5280,
    ".ovl_i1":         0x1B91E0,
    ".ovl_i2":         0x1BC7F0,
    ".ovl_i3":         0x1BDFE0,
    ".ovl_i4":         0x1BFDE0,
    ".ovl_i5":         0x1C2150,
    ".ovl_i6":         0x1C36C0,
    ".seg_1C3780":     0x1C3CB0,
    ".seg_1C3D00":     0x1C43B0,
    ".ovl_i7":         0x1C4910,
    ".ovl_i8":         0x1C61E0,
    ".ovl_i9":         0x1C8F90,
    ".ovl_i10":        0x1CA3F0,
    ".ovl_i11":        0x1CADD0,
    ".ovl_i12":        0x1CBAA0,
    ".ovl_i13":        0x1CF040,
    ".ovl_i14":        0x1CFA70,
    ".ovl_i15":        0x1D10B0,
}


def get_text_size(sec: dict) -> int:
    """Get the size of the text (code) portion of a section."""
    name = sec["name"]
    if "text_vram_end" in sec:
        return sec["text_vram_end"] - sec["vram"]
    text_rom_end = OVERLAY_TEXT_ROM_ENDS.get(name)
    if text_rom_end:
        return text_rom_end - sec["rom"]
    return sec["size"]


# ---------------------------------------------------------------------------
# Explicit function name sets (authoritative)
# ---------------------------------------------------------------------------

# These are functions confirmed by examining the symbol files.
# Only symbols explicitly in these sets or matching func_ prefix are classified
# as functions; everything else is treated as data.

CONFIRMED_FUNCS = set()

# From audio_symbols.txt "// Functions" section
CONFIRMED_FUNCS.update({
    "Audio_DmaCopyImmediate", "Audio_DmaCopyAsync", "Audio_DmaPartialCopyAsync",
    "AudioLoad_DecreaseSampleDmaTtls", "AudioLoad_DmaSampleData",
    "AudioLoad_InitSampleDmaBuffers", "Audio_PatchSound", "Audio_PatchBank",
    "Audio_BankLoadImmediate", "Audio_BankLoadAsync",
    "AudioLoad_SequenceDmaImmediate", "AudioLoad_SequenceDmaAsync",
    "AudioLoad_GetMissingBank", "Audio_LoadBanksImmediate",
    "Audio_PreLoadSequence", "Audio_LoadSequence", "Audio_LoadSequenceInternal",
    "AudioHeap_AllocZeroed", "AudioHeap_AllocCached",
    "AudioHeap_SearchRegularCaches", "AudioHeap_ResetStep",
    "AudioThread_Init", "AudioHeap_InitMainPools",
    "RootNewtonStep", "KTHRoot", "BuildVolRampingsTBL",
    "AudioHeap_ResetLoadStatus", "AudioHeap_DiscardSequence",
    "AudioHeap_DiscardFont", "AudioHeap_InitPool",
    "AudioHeap_InitPersistentCache", "AudioHeap_InitTemporaryCache",
    "AudioHeap_ResetPool", "AudioHeap_InitSessionPools",
    "AudioHeap_InitCachePools", "AudioHeap_InitPersistentPoolsAndCaches",
    "AudioHeap_InitTemporaryPoolsAndCaches", "AudioHeap_UpdateReverbs",
    "AudioHeap_Init", "Audio_NoteInitAll", "Audio_InitNoteFreeList",
    "AudioSeq_AudioListPushBack", "AudioSeq_ResetSequencePlayer",
    "AudioSeq_SequencePlayerDisable", "AudioSeq_InitSequencePlayers",
    "AudioSeq_InitLayerFreelist", "AudioSeq_SequencePlayerProcessSequence",
    "AudioSeq_ScriptReadU8", "AudioSeq_ScriptReadS16",
    "AudioSeq_ScriptReadCompressedU16", "AudioSeq_SequenceChannelProcessScript",
    "AudioSeq_SequenceChannelEnable", "AudioSeq_SequencePlayerSetupChannels",
    "AudioSeq_SequencePlayerDisableChannels", "AudioSeq_SeqLayerProcessScript",
    "AudioSeq_SequenceChannelSetVolume", "AudioSeq_SeqChannelSetLayer",
    "AudioSeq_SeqLayerFree", "AudioSeq_SetInstrument",
    "AudioSeq_GetInstrument", "AudioSeq_InitSequenceChannel",
    "AudioSeq_SeqLayerDisable", "AudioSeq_RequestFreeSeqChannel",
    "AudioSynth_InitNextReverbRingBuf", "AudioSynth_ApplyHaasEffect",
    "AudioSynth_SaveReverbRingBufferPart", "AudioSynth_SaveReverbSamples",
    "AudioSynth_LoadReverbSamples", "AudioSynth_LoadReverbRingBufferPart",
    "AudioSynth_Update", "AudioSeq_ProcessSequences",
    "AudioSynth_SyncSampleStates", "AudioSynth_DoOneAudioUpdate",
    "Audio_AllocNote", "Audio_ProcessNotes",
    "Audio_NoteVibratoInit", "Audio_AdsrUpdate",
    "Audio_NoteVibratoUpdate", "Audio_NoteDisable",
    "Audio_AudioListRemove", "Audio_InitNoteLists", "Audio_InitNoteList",
    "Audio_BuildSyntheticWave", "Audio_InitSyntheticWave",
    "Audio_SeqLayerNoteRelease", "Audio_SeqLayerDecayRelease",
    "Audio_SeqLayerNoteDecay", "AudioSeq_SequenceChannelDisable",
    "Audio_AudioListPushFront", "Audio_AdsrInit",
    "Audio_NoteInit", "Audio_GetDrum", "Audio_GetInstrument",
    "Audio_GetInstrumentTunedSample", "Audio_NoteSetResamplingRate",
    "Audio_InitNoteSub", "Audio_AllocNoteFromActive",
    "Audio_FindNodeWithPrioLessThan",
    "Audio_NoteReleaseAndTakeOwnership", "AudioSeq_AudioListPopBack",
    "Audio_AllocNoteFromDecaying", "Audio_NoteInitForLayer",
    "Audio_AllocNoteFromDisabled", "Audio_NotePoolFill", "Audio_NotePoolClear",
    "Audio_SequenceChannelProcessSound", "Audio_SequencePlayerProcessSound",
    "Audio_GetPortamentoFreqScale", "Audio_GetVibratoPitchChange",
    "Audio_GetVibratoFreqScale",
    "AudioThread_CreateTask", "AudioThread_InitQueues",
    "AudioThread_SetFadeInTimer", "AudioThread_SetFadeOutTimer",
    "AudioThread_ProcessGlobalCmd", "AudioThread_QueueCmd",
    "AudioThread_QueueCmdF32", "AudioThread_QueueCmdS32",
    "AudioThread_ScheduleProcessCmds", "AudioThread_ProcessCmds",
    "AudioSynth_LoadWaveSamples", "AudioSynth_ProcessEnvelope",
    "AudioSynth_FinalResample", "AudioSynth_ProcessNote",
    "AudioGeneral_DisableSeqPlayer2", "AudioThread_QueueCmdS8",
    "AudioLoad_Init",
})

# From libultra_symbols.txt - explicitly known functions
CONFIRMED_FUNCS.update({
    "alSynFreeFX", "osViSwapBuffer", "osViSetSpecialFeatures",
    "osVirtualToPhysical", "osSendMesg", "osGetTime", "osSetTime",
    "osContStartReadData", "osContGetReadData", "__osPackReadData",
    "osRecvMesg", "osDpGetStatus", "osViSetMode",
    "osSpTaskYield", "_VirtualToPhysicalTask", "osSpTaskStartGo",
    "osDpSetStatus", "osCreateMesgQueue", "osSetEventMesg",
    "osViSetEvent", "osCreateThread", "osStartThread",
    "osSpTaskLoad", "osViBlack", "osViGetCurrentFramebuffer",
    "osCreatePiManager", "osSetThreadPri", "sqrtf",
    "guOrthoF", "guOrtho", "guTranslateF", "guTranslate",
    "osEepromLongRead", "osEepromProbe", "osPhysicalToVirtual",
    "sprintf", "proutSprintf", "osInvalDCache", "osPiStartDma",
    "osInvalICache", "bzero", "osAiSetFrequency",
    "osAiSetNextBuffer", "osAiGetLength",
    "__osProbeTLB", "__osDisableInt", "__osRestoreInt",
    "__osDequeueThread", "__osEnqueueAndYield", "__osEnqueueThread",
    "__osPopThread", "__osDispatchThread", "__osCleanupThread",
    "osGetCount", "__osSiCreateAccessQueue", "__osSiGetAccess",
    "__osSiRelAccess", "__osSiRawStartDma", "__osSpSetStatus",
    "osWritebackDCache", "__osSpDeviceBusy", "osGetThreadPri",
    "__osViGetCurrentContext", "__osPiCreateAccessQueue",
    "osPiRawStartDma", "__osDevMgrMain",
    "__ll_div", "__ll_mul", "osSetTimer",
    "guMtxIdentF", "osEepromRead", "memcpy", "strlen",
    "__osAiDeviceBusy", "__osSetCompare", "__osSiDeviceBusy",
    "_Litob", "osJamMesg", "osPiGetCmdQueue",
    "osDestroyThread", "_Ldtob", "__osAtomicDec",
    "lldiv", "ldiv",
    "osPfsDeleteFile", "__osPfsReleasePages", "__osBlockSum",
    "_Printf", "osInitialize", "osWritebackDCacheAll",
    "__osSetSR", "__osGetSR", "__osSetFpcCsr",
    "__osSiRawReadIo", "__osSiRawWriteIo", "osMapTLBRdb",
    "osContInit", "__osPiGetAccess", "__osPiRelAccess",
    "guMtxF2L", "__osPackRamReadData", "__osContDataCrc",
    "__osPfsGetStatus", "osPfsInit", "__osEepStatus",
    "__osContRamRead", "__osContAddressCrc",
    "__osPackRamWriteData", "__osContRamWrite",
    "__osViSwapContext", "strchr", "__osViInit",
    "viMgrMain", "osCreateViManager", "__osPackRequestData",
    "__osContGetInitData", "__osInsertTimer",
    "__osTimerServicesInit", "__osTimerInterrupt",
    "__osSetTimerIntr", "__osCheckId", "__osPfsSelectBank",
    "__osPfsRWInode", "__osRepairPackId", "__osCheckPackId",
    "__osSumcalc", "__osIdCheckSum", "osPfsChecker",
    "corrupted_init", "corrupted", "osEepromWrite",
    "__osPackEepWriteData", "__osPackEepReadData",
    "__osSpSetPc", "__osSpRawStartDma", "__osSpGetStatus",
    "osSpTaskYielded", "osEepromLongWrite",
    "__osGetCause", "__osGetId", "guMtxIdent", "guMtxL2F",
    "__osSyncPutChars", "osPiRawReadIo", "send_packet",
    "__osClearPage", "osPfsFindFile", "__osPfsDeclearPage",
    "osPfsFreeBlocks", "osPfsAllocateFile", "__osPfsGetNextPage",
    "osPfsReadWriteFile", "__osPfsRequestData", "__osPfsGetInitData",
    "osPfsIsPlug", "osPfsNumFiles",
    "guLookAtHiliteF", "guLookAtHilite",
    "guLookAtReflectF", "guLookAtReflect",
    "bcopy", "_bnkfPatchBank", "alBnkfNew", "bnkf_stub",
    "__osException", "__osExceptionPreamble",
    "osSetIntMask", "kdebugserver", "_Putfld",
    "__ull_div", "__ull_rshift", "__ull_rem",
    "__ll_lshift", "__ll_rem", "__ull_divremi", "__ll_mod", "__ll_rshift",
    "osPfsFileState", "alSeqFileNew",
})

# From symbol_addrs.txt - game functions
CONFIRMED_FUNCS.update({
    "bootproc", "main_thread",
    "SysUtils_Srand", "SysUtils_Rand", "SysUtils_MtxToMtxF",
    "SysUtils_MtxFToMtx", "SysUtils_LightsSetAmbient",
    "SysUtils_LightsSetColor", "SysUtils_LightsSetDirection",
    "SysUtils_LightsSetSource", "SysUtils_MatrixAffineMultiply",
    "SysUtils_UpdateControllers", "SysUtils_ContInitialize",
    "SysUtils_MatrixLookAt", "SysUtils_InterpolateMtx",
    "SysUtils_NormalizeVertexTri",
    "configSignalRectangle", "AudioThread_QueueCmdS8",
    "Mio0_Decompress", "Main_IdleThread",
    "SysMain_GfxFullSync", "SysMain_SendGfxTaskSetMesg",
    "SysMain_GfxInitBuffers", "Draw_WaterEffects",
    "GameLoad_LoadOverlay", "GameLoad_LoadCodeseg",
    "Libc_strncpy", "Libc_strcmp", "Libc_strncmp",
    "SysUtils_TaylorSeries", "AudioSynth_ProcessNote",
    "Math_Normalize_VectorComponents", "Math_Fabs",
    "Math_Vec3f_Set", "Math_Vec3f_Initialize", "Math_Vec3f_Copy",
    "Math_Vec3f_Substract", "Math_Normalize_Angle",
    "SysUtils_Round", "Math_srand", "Math_Rand",
    "SysMain_CreateGfxTask", "SegmentedToVirtual", "Strlen2",
    "Save_PfsIsPlug", "Save_PfsDeleteFile", "Save_PfsFindFile",
    "Save_PfsCheckFree", "Save_GenCheckSum",
    "game_dma_copy", "unk_game_load",
    "SysMain_Thread",
    "FadeTransition_SetProps",
})

# From files/symbol_addrs.txt - extra functions
CONFIRMED_FUNCS.update({
    "n_alSeqpDelete", "osSyncPrintf", "n_alSynFreeFX",
    "n_alSynRemovePlayer", "leoInitUnit_atten", "myfree",
    "osVoiceInit", "guMtxXFMF", "guRotateRPY", "guAlign",
    "guFrustum_UNUSED", "guRotateRPYF", "guAlignF", "guFrustumF2",
})

# Splat auto-generated function names from files/symbol_addrs.txt
CONFIRMED_FUNCS.update({
    "contreaddata_text_017C", "conteepread_text_01F0",
    "conteepwrite_text_01B0", "xprintf_text_082C",
    "kdebugserver_text_0220", "kdebugserver_text_026C",
    "xldtob_text_0600", "xldtob_text_06E0",
    "sprintf_text_006C",
    "MusPtrBankGetCurrent",
})


# ---------------------------------------------------------------------------
# Symbol data class
# ---------------------------------------------------------------------------

class Symbol:
    """Represents a parsed symbol."""

    def __init__(self, name: str, vram: int, source: str):
        self.name = name
        self.vram = vram
        self.source = source
        self.is_func: Optional[bool] = None  # None = not yet decided
        self.explicit_size: Optional[int] = None
        self.segment_hint: Optional[str] = None
        self.ignore: bool = False

    def __repr__(self):
        kind = "func" if self.is_func else ("data" if self.is_func is False else "?")
        return f"Sym({self.name} @ 0x{self.vram:08X} [{kind}])"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_symbol_line(line: str, source: str) -> Optional[Symbol]:
    """Parse one line from a splat symbol_addrs file."""
    stripped = line.strip()
    if not stripped or stripped.startswith("//") or stripped.startswith("#"):
        return None

    m = re.match(r'^\s*(\w+)\s*=\s*(0x[0-9a-fA-F]+)\s*;?\s*(//.*)?$', stripped)
    if not m:
        return None

    name = m.group(1)
    try:
        vram = int(m.group(2), 16)
    except ValueError:
        return None

    sym = Symbol(name, vram, source)
    comment = m.group(3) or ""

    # type:func / type:data / type:jtbl
    tm = re.search(r'type:(\w+)', comment)
    if tm:
        t = tm.group(1).lower()
        if t == "func":
            sym.is_func = True
        else:
            sym.is_func = False

    # size:0xNN
    sm = re.search(r'size:(0x[0-9a-fA-F]+|\d+)', comment)
    if sm:
        sym.explicit_size = int(sm.group(1), 0)

    # segment:xxx
    sg = re.search(r'segment:(\w+)', comment)
    if sg:
        sym.segment_hint = sg.group(1)

    # ignore:true
    if "ignore:true" in comment:
        sym.ignore = True

    # name_end: -> linker range marker, not a function
    if "name_end:" in comment:
        sym.is_func = False

    # defined:true -> (informational, doesn't determine func vs data alone)

    return sym


def parse_symbol_file(filepath: str, source: str) -> List[Symbol]:
    """Parse a symbol file, return list of Symbol."""
    if not os.path.exists(filepath):
        print(f"  WARNING: not found: {filepath}", file=sys.stderr)
        return []
    syms = []
    with open(filepath) as f:
        for line in f:
            s = parse_symbol_line(line, source)
            if s:
                syms.append(s)
    return syms


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_symbol(sym: Symbol) -> bool:
    """Return True if the symbol should be treated as a function."""
    if sym.ignore:
        return False

    # If already classified by type: annotation
    if sym.is_func is not None:
        return sym.is_func

    name = sym.name

    # 1. Check confirmed function set (authoritative)
    if name in CONFIRMED_FUNCS:
        return True

    # 2. func_XXXXXXXX prefix -> always a function
    if name.startswith("func_"):
        return True

    # 3. D_ prefix -> always data
    if name.startswith("D_"):
        return False

    # 4. Jump table
    if name.startswith("jtbl_"):
        return False

    # 5. ROM linker symbols
    if "_ROM_START" in name or "_ROM_END" in name:
        return False

    # 6. Section markers
    for marker in ("TextStart", "TextEnd", "DataStart", "DataEnd",
                    "textStart", "textEnd", "dataStart", "dataEnd"):
        if marker in name:
            return False

    # 7. BSS / data / rodata auto-names
    if re.match(r'^\w+_bss_\w+$', name):
        return False
    if re.match(r'^[a-z]+_data_[0-9A-Fa-f]+$', name):
        return False
    if re.match(r'^[a-z]+_rodata_[0-9A-Fa-f]+$', name):
        return False

    # 8. Splat auto text names -> functions
    if re.match(r'^[a-z]+_text_[0-9A-Fa-f]+$', name):
        return True

    # 9. Default: not a function (conservative)
    return False


# ---------------------------------------------------------------------------
# Overlay function scanning from C source files
# ---------------------------------------------------------------------------

# Map overlay section names to the prefix used in symbol names
OVERLAY_PREFIX_MAP = {
    ".segment_1B1FB0": "1B1FB0",
    ".ovl_i0":  "i0",
    ".ovl_i1":  "i1",
    ".ovl_i2":  "i2",
    ".ovl_i3":  "i3",
    ".ovl_i4":  "i4",
    ".ovl_i5":  "i5",
    ".ovl_i6":  "i6",
    ".seg_1C3780": "1C3780",
    ".seg_1C3D00": "1C3D00",
    ".ovl_i7":  "i7",
    ".ovl_i8":  "i8",
    ".ovl_i9":  "i9",
    ".ovl_i10": "i10",
    ".ovl_i11": "i11",
    ".ovl_i12": "i12",
    ".ovl_i13": "i13",
    ".ovl_i14": "i14",
    ".ovl_i15": "i15",
}

# Reverse: prefix -> section name
PREFIX_TO_SECTION = {v: k for k, v in OVERLAY_PREFIX_MAP.items()}

# Source directories to scan for overlay functions
OVERLAY_SOURCE_DIRS = [
    "src/overlays",
    "src",
]


def scan_for_overlay_funcs(decomp_path: str) -> Dict[str, List[Tuple[str, int, Optional[int]]]]:
    """
    Scan C source files for overlay function names.
    
    Looks for patterns like:
      - func_i1_802C5800 (function definitions, declarations, calls)
      - func_1B1FB0_802C5800
      - GLOBAL_ASM("asm/.../func_i2_802C5800.s")
    
    Extracts the VRAM address from the name and maps to the correct overlay.
    """
    result: Dict[str, List[Tuple[str, int, Optional[int]]]] = {}
    
    # Regex: match func_PREFIX_XXXXXXXX where PREFIX is iN, 1B1FB0, 1C3780, 1C3D00
    # Build prefix alternation
    prefixes = "|".join(re.escape(p) for p in sorted(PREFIX_TO_SECTION.keys(), key=len, reverse=True))
    func_name_re = re.compile(
        r'\bfunc_(' + prefixes + r')_(80[0-9A-Fa-f]{6})\b'
    )
    
    # Scan all C files in overlay source directories
    seen: Dict[str, set] = {}  # section_name -> set of vrams
    
    for src_dir in OVERLAY_SOURCE_DIRS:
        full_dir = os.path.join(decomp_path, src_dir)
        if not os.path.isdir(full_dir):
            continue
            
        for root, dirs, files in os.walk(full_dir):
            for fname in files:
                if not fname.endswith(".c"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath) as f:
                        content = f.read()
                except (OSError, IOError):
                    continue
                    
                for m in func_name_re.finditer(content):
                    prefix = m.group(1)
                    vram_hex = m.group(2)
                    vram = int(vram_hex, 16)
                    func_name = f"func_{prefix}_{vram_hex}"
                    
                    sec_name = PREFIX_TO_SECTION.get(prefix)
                    if not sec_name:
                        continue
                    
                    if sec_name not in seen:
                        seen[sec_name] = set()
                    if vram not in seen[sec_name]:
                        seen[sec_name].add(vram)
                        if sec_name not in result:
                            result[sec_name] = []
                        result[sec_name].append((func_name, vram, None))
    
    # Also check for named overlay functions (e.g., FadeTransition_SetProps)
    # These come from ovl_symbols.txt and will be handled by assign_section()
    
    return result


# ---------------------------------------------------------------------------
# Section assignment
# ---------------------------------------------------------------------------

def assign_section(sym: Symbol) -> Optional[dict]:
    """Determine which section a function symbol belongs to."""
    vram = sym.vram
    name = sym.name

    # 1. Explicit segment hint from annotation
    if sym.segment_hint:
        hint = sym.segment_hint.lower()
        for sec in OVERLAY_SECTIONS:
            if sec["name"].lstrip(".").lower() == hint:
                return sec

    # 2. Overlay naming: func_iN_ or iN_ or 1B1FB0_ etc.
    ovl_match = re.match(r'^(?:func_)?i(\d+)_', name, re.IGNORECASE)
    if ovl_match:
        ovl_num = int(ovl_match.group(1))
        target = f".ovl_i{ovl_num}"
        for sec in OVERLAY_SECTIONS:
            if sec["name"] == target:
                return sec

    if name.lower().startswith("1b1fb0_"):
        for sec in OVERLAY_SECTIONS:
            if sec["name"] == ".segment_1B1FB0":
                return sec

    if name.lower().startswith("1c3780_"):
        for sec in OVERLAY_SECTIONS:
            if sec["name"] == ".seg_1C3780":
                return sec

    if name.lower().startswith("1c3d00_"):
        for sec in OVERLAY_SECTIONS:
            if sec["name"] == ".seg_1C3D00":
                return sec

    # 3. Main sections by VRAM range
    for sec in MAIN_SECTIONS:
        sec_start = sec["vram"]
        text_end = sec.get("text_vram_end", sec_start + sec["size"])
        if sec_start <= vram < text_end:
            return sec

    return None


# ---------------------------------------------------------------------------
# Size calculation
# ---------------------------------------------------------------------------

def calculate_sizes(
    section_funcs: Dict[str, List[Tuple[str, int, Optional[int]]]],
    all_sections: List[dict]
) -> Dict[str, List[Tuple[str, int, int]]]:
    """
    Sort functions by VRAM per section, deduplicate, compute sizes.
    """
    result = {}
    section_map = {s["name"]: s for s in all_sections}

    for sec_name, funcs in section_funcs.items():
        funcs.sort(key=lambda x: x[1])

        # Deduplicate by VRAM, prefer named over func_XXXXX
        vram_map: Dict[int, Tuple[str, Optional[int]]] = {}
        for name, vram, expl_size in funcs:
            existing = vram_map.get(vram)
            is_auto = name.startswith("func_") or re.match(r'^[a-z]+_text_', name)
            if existing:
                existing_auto = existing[0].startswith("func_") or re.match(r'^[a-z]+_text_', existing[0])
                if existing_auto and not is_auto:
                    vram_map[vram] = (name, expl_size or existing[1])
                elif expl_size and not existing[1]:
                    vram_map[vram] = (existing[0], expl_size)
            else:
                vram_map[vram] = (name, expl_size)

        sorted_funcs = sorted(vram_map.items(), key=lambda x: x[0])

        sec = section_map.get(sec_name)
        text_size = get_text_size(sec) if sec else 0
        sec_text_end = sec["vram"] + text_size if sec else 0

        sized = []
        for i, (vram, (name, expl_size)) in enumerate(sorted_funcs):
            if expl_size and expl_size > 0:
                size = expl_size
            elif i + 1 < len(sorted_funcs):
                size = sorted_funcs[i + 1][0] - vram
            else:
                # Last function: extend to text end
                size = sec_text_end - vram if sec_text_end > vram else 0x10
                if size <= 0:
                    size = 0x10

            # Clamp unreasonable sizes
            if size <= 0:
                size = 0x4
            if size > 0x20000:  # >128KB is suspicious for a single function
                size = 0x20000

            sized.append((name, vram, size))

        result[sec_name] = sized

    return result


# ---------------------------------------------------------------------------
# TOML output
# ---------------------------------------------------------------------------

def write_toml(output_path: str, all_sections: List[dict],
               section_funcs: Dict[str, List[Tuple[str, int, int]]]):
    """Write the N64Recomp symbols TOML file.
    
    N64Recomp requires every [[section]] to have a 'functions' key that is an
    array.  When there are no functions we emit ``functions = []`` explicitly;
    otherwise we use TOML array-of-tables syntax (``[[section.functions]]``).
    """
    with open(output_path, "w") as f:
        f.write("# Wave Race 64 (USA Rev 1) Symbol File for N64Recomp\n")
        f.write("# Auto-generated by generate_symbols.py from decomp project data.\n")
        f.write("#\n")
        f.write("# Sources:\n")
        f.write("#   linker_scripts/us/rev1/symbol_addrs.txt\n")
        f.write("#   linker_scripts/us/rev1/audio_symbols.txt\n")
        f.write("#   linker_scripts/us/rev1/libultra_symbols.txt\n")
        f.write("#   linker_scripts/us/rev1/ovl_symbols.txt\n")
        f.write("#   files/symbol_addrs.txt\n")
        f.write("#   waverace64.us.rev1.yaml (splat config)\n")
        f.write("#   C source files (overlay functions)\n")
        f.write("\n")

        for sec in all_sections:
            name = sec["name"]
            funcs = section_funcs.get(name, [])

            f.write(f"# {'=' * 77}\n")
            f.write(f"# {name} ({len(funcs)} functions)\n")
            f.write(f"# {'=' * 77}\n")
            f.write("[[section]]\n")
            f.write(f'name = "{name}"\n')
            f.write(f"rom = 0x{sec['rom']:08X}\n")
            f.write(f"vram = 0x{sec['vram']:08X}\n")
            f.write(f"size = 0x{sec['size']:X}\n")

            if not funcs:
                # N64Recomp requires the functions key to exist as an array
                # even when empty.  Without this the parser throws:
                #   "Invalid functions array"
                f.write("functions = []\n")
            f.write("\n")

            for func_name, vram, size in funcs:
                f.write("[[section.functions]]\n")
                f.write(f'name = "{func_name}"\n')
                f.write(f"vram = 0x{vram:08X}\n")
                f.write(f"size = 0x{size:X}\n")
                f.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate N64Recomp symbols TOML from Wave Race 64 decomp"
    )
    parser.add_argument(
        "--decomp", default="../Wave-Race-64",
        help="Path to the decomp project (default: ../Wave-Race-64)"
    )
    parser.add_argument(
        "--output", default="recomp/waverace64.us.rev1.syms.toml",
        help="Output TOML path (default: recomp/waverace64.us.rev1.syms.toml)"
    )
    args = parser.parse_args()

    decomp = os.path.abspath(args.decomp)
    output = args.output

    print(f"Decomp project: {decomp}")
    print(f"Output TOML:    {output}")
    print()

    # -------------------------------------------------------------------
    # 1. Parse all symbol files
    # -------------------------------------------------------------------
    print("Parsing symbol files...")
    all_symbols: List[Symbol] = []

    files_to_parse = [
        ("linker_scripts/us/rev1/symbol_addrs.txt", "symbol_addrs"),
        ("linker_scripts/us/rev1/audio_symbols.txt", "audio_symbols"),
        ("linker_scripts/us/rev1/libultra_symbols.txt", "libultra_symbols"),
        ("linker_scripts/us/rev1/ovl_symbols.txt", "ovl_symbols"),
        ("files/symbol_addrs.txt", "files_symbol_addrs"),
    ]

    for relpath, source in files_to_parse:
        fullpath = os.path.join(decomp, relpath)
        syms = parse_symbol_file(fullpath, source)
        print(f"  {source:30s}: {len(syms):4d} symbols")
        all_symbols.extend(syms)

    print(f"  Total raw symbols: {len(all_symbols)}")
    print()

    # -------------------------------------------------------------------
    # 2. Classify symbols
    # -------------------------------------------------------------------
    print("Classifying symbols...")
    func_symbols = []
    data_count = 0
    ignored_count = 0

    for sym in all_symbols:
        if sym.ignore:
            ignored_count += 1
            continue
        if classify_symbol(sym):
            sym.is_func = True
            func_symbols.append(sym)
        else:
            data_count += 1

    print(f"  Functions: {len(func_symbols)}")
    print(f"  Data:      {data_count}")
    print(f"  Ignored:   {ignored_count}")
    print()

    # -------------------------------------------------------------------
    # 3. Scan overlay C sources for additional functions
    # -------------------------------------------------------------------
    print("Scanning overlay C sources...")
    overlay_funcs = scan_for_overlay_funcs(decomp)
    ovl_count = sum(len(v) for v in overlay_funcs.values())
    print(f"  Found {ovl_count} functions from overlay C sources")
    for sec_name, funcs in sorted(overlay_funcs.items()):
        print(f"    {sec_name:25s}: {len(funcs):4d}")
    print()

    # -------------------------------------------------------------------
    # 4. Assign functions to sections
    # -------------------------------------------------------------------
    print("Assigning functions to sections...")

    all_sections = MAIN_SECTIONS + OVERLAY_SECTIONS

    section_funcs_raw: Dict[str, List[Tuple[str, int, Optional[int]]]] = {
        s["name"]: [] for s in all_sections
    }

    # Assign symbol-file functions
    unassigned = []
    for sym in func_symbols:
        sec = assign_section(sym)
        if sec is None:
            unassigned.append(sym)
            continue
        section_funcs_raw[sec["name"]].append((sym.name, sym.vram, sym.explicit_size))

    # Add overlay functions from C source scan
    for sec_name, funcs in overlay_funcs.items():
        section_funcs_raw[sec_name].extend(funcs)

    # Print stats
    for sec in all_sections:
        count = len(section_funcs_raw[sec["name"]])
        if count > 0:
            print(f"  {sec['name']:25s}: {count:4d} functions")

    if unassigned:
        print(f"\n  INFO: {len(unassigned)} functions not assigned (outside known text sections):")
        for sym in unassigned[:10]:
            print(f"    {sym.name} @ 0x{sym.vram:08X} (source: {sym.source})")
        if len(unassigned) > 10:
            print(f"    ... and {len(unassigned) - 10} more")
    print()

    # -------------------------------------------------------------------
    # 5. Calculate sizes
    # -------------------------------------------------------------------
    print("Calculating function sizes...")
    section_funcs_sized = calculate_sizes(section_funcs_raw, all_sections)

    # -------------------------------------------------------------------
    # 6. Write TOML
    # -------------------------------------------------------------------
    print(f"Writing TOML to {output}...")
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    write_toml(output, all_sections, section_funcs_sized)

    # -------------------------------------------------------------------
    # 7. Print summary
    # -------------------------------------------------------------------
    total_funcs = sum(len(v) for v in section_funcs_sized.values())
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total functions in TOML: {total_funcs}")
    print()
    print(f"{'Section':<25s} {'Functions':>10s} {'ROM':>12s} {'VRAM':>12s} {'Size':>10s}")
    print("-" * 69)
    for sec in all_sections:
        name = sec["name"]
        funcs = section_funcs_sized.get(name, [])
        print(f"{name:<25s} {len(funcs):>10d} 0x{sec['rom']:08X} 0x{sec['vram']:08X} 0x{sec['size']:>6X}")
    print("-" * 69)
    print(f"{'TOTAL':<25s} {total_funcs:>10d}")
    print()

    # Validation
    warnings = 0
    for sec_name, funcs in section_funcs_sized.items():
        for name, vram, size in funcs:
            if size <= 0:
                print(f"  WARNING: {name} in {sec_name}: size={size}")
                warnings += 1
            if size > 0x10000:
                print(f"  WARNING: {name} in {sec_name}: very large size 0x{size:X}")
                warnings += 1

    overlay_populated = sum(1 for sec in OVERLAY_SECTIONS if section_funcs_sized.get(sec["name"]))
    print(f"Overlay sections populated: {overlay_populated}/{len(OVERLAY_SECTIONS)}")
    if warnings:
        print(f"Warnings: {warnings}")
    else:
        print("No warnings.")
    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

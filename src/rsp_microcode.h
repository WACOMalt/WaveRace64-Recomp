/**
 * @file rsp_microcode.h
 * @brief RSP microcode dispatch for WaveRace64-Recomp.
 *
 * Wave Race 64 uses the F3DEX microcode (a variant of Fast3D) for its
 * display list processing. This module maps OSTask types to the
 * appropriate RSP microcode handler functions.
 */

#ifndef WR64_RSP_MICROCODE_H
#define WR64_RSP_MICROCODE_H

#include "librecomp/rsp.hpp"

namespace wr64 {

/**
 * RSP microcode dispatch callback.
 *
 * Matches recomp::rsp::callbacks_t::get_rsp_microcode_t signature.
 * Given an OSTask, returns a pointer to the appropriate RSP microcode
 * function, or nullptr if no matching microcode is found.
 *
 * @param task The OSTask describing the RSP task to execute.
 * @return Function pointer to the RSP microcode handler, or nullptr.
 */
RspUcodeFunc* get_rsp_microcode(const OSTask* task);

} // namespace wr64

#endif // WR64_RSP_MICROCODE_H

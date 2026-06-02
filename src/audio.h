/**
 * @file audio.h
 * @brief Audio callbacks for WaveRace64-Recomp.
 *
 * Provides SDL2-based audio output callbacks that match the
 * ultramodern::audio_callbacks_t interface.
 */

#ifndef WR64_AUDIO_H
#define WR64_AUDIO_H

#include <cstdint>
#include <cstddef>

namespace wr64 {

/**
 * Queue audio samples for playback.
 *
 * @param samples  Pointer to interleaved stereo 16-bit PCM samples.
 * @param count    Number of samples (not bytes — each sample is one int16_t).
 */
void audio_queue_samples(int16_t* samples, size_t count);

/**
 * Get the number of audio frames remaining in the playback buffer.
 *
 * @return Number of samples still queued for playback.
 */
size_t audio_get_frames_remaining();

/**
 * Set the audio playback frequency.
 *
 * @param freq  Sample rate in Hz (e.g., 32000 for N64 audio).
 */
void audio_set_frequency(uint32_t freq);

} // namespace wr64

#endif // WR64_AUDIO_H

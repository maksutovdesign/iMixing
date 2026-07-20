# iMixing V2: Audio Quality Plan

## Product position

iMixing V2 is a controlled first-pass mixing and mastering system. It should not claim to replace a mixing engineer on every production. Its promise is to create a transparent, measurable starting point and show when a human review is needed.

## Delivered in this foundation update

- Loudness payloads include integrated LUFS, true peak, short-term maximum, loudness range, and crest factor.
- True peak uses 4x band-limited oversampling when SciPy is available. The fallback reports only sample-peak-safe behavior rather than pretending linear interpolation is true peak measurement.
- The mastering target now controls its dBTP ceiling as well as LUFS target.
- The renderer no longer raises gain a second time after limiting, which could have invalidated the final true-peak ceiling.
- Every audio job exposes a quality report with source clipping, loudness/peak deltas, transient warnings, and concrete review suggestions.

## Next algorithm milestones

1. Add an instrument-aware classifier that uses filename hints as an override, not the primary decision.
2. Add cross-stem masking analysis and restricted dynamic EQ moves for kick/bass and vocal/music conflicts.
3. Add reference-track matching for tonal balance, dynamics, stereo width, and loudness. Keep all adjustments bounded and show the deltas.
4. Produce `safe` and `loud` master variants from one premaster, with a user-selected distribution profile.
5. Add a listening-test corpus of licensed stems and regression checks for clipping, phase, loudness, timing, and output stability.
6. Move DSP jobs to the VPS worker. Shared hosting remains a product demo only.

## MIDI Doctor V2 principles

- Preserve already expressive timing and velocity by default.
- Apply quantization and humanization at phrase and instrument level, not as random per-note noise.
- Treat drums, bass, harmony, and melody as separate musical problems.
- Make each edit explainable in the returned report.

## Acceptance criteria

- A job never reports a true-peak ceiling it has exceeded.
- A result that cannot safely reach the loudness target explains why.
- Quality reports identify clipped sources and excessive limiting.
- Changes are covered by API and unit tests before deployment.

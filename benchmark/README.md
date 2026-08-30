# Benchmark entry — board 1 of 32

[metadata.json](metadata.json) is the supplied catalogue entry for this board,
preserved byte for byte from the seed pack. It is the same record that appears
in `boards_index.json` in
[PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench), and the two must agree.

| | |
|---|---|
| Repository | `PCBA_StatusBeacon` |
| Board id | `status_beacon` |
| Category | simple-digital |
| Difficulty | 1 / 5 |
| Brief detail | 1 / 5 |
| Likely layer count | 2 |
| Primary stressors | basic component selection, simple placement/routing, LED current limiting, connector access |

`difficulty` is how hard the board is. `detail` is how much of it the brief
states — and a low `detail` is not a low bar. A detail-1 brief leaves the
architecture open on purpose, and an agent that fills the silence with invented
user requirements has failed the board more thoroughly than one that designs it
badly.

At difficulty 1/5 and detail 1/5 in the `simple-digital` category, this board tests whether a design agent can execute competently with almost no specification handed to it — the metadata's stressors are basic component selection, simple placement/routing, LED current limiting, and connector access. The interesting question is not whether the circuit is hard, but whether the agent makes and justifies its own choices (MCU, LED technology, shape, connector family) instead of fabricating requirements the brief never stated. Two of those stressors — LED current limiting and connector access — are where the missing detail bites hardest: with no brightness, current, environment or mechanical context stated, the per-LED current, the total the board draws from USB with the whole array lit, and the physical usability of the connectors all have to be derived and shown rather than asserted.

## What goes here

Compact results only: metrics, verdicts, and the commit each was measured at.
The evidence for a result is the artefact the toolkit recomputes, not a summary
of it.

Routing search output, candidate pools, build trees and field-solver dumps do
**not** go here. They are ignored by [.gitignore](../.gitignore) and are
regenerated from what is committed. Thirty-two repositories share one benchmark
clone; weight here is paid thirty-two times.

## Protocol

The attempt protocol is defined once, in the umbrella repository, so that
thirty-two boards cannot drift into thirty-two protocols. See
[PCBA_AutoDesignAndTest_Bench/BENCHMARK.md](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench/blob/main/BENCHMARK.md).

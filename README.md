# Status Beacon Controller

A small USB-powered status beacon board: a microcontroller, one pushbutton, at least eight individually controllable RGB LEDs, and a small programming/debug connector.

`PCBA_StatusBeacon` is the benchmark's Status Beacon Controller: a small, USB-powered board carrying a microcontroller, one pushbutton, at least eight individually controllable RGB LEDs, and a small programming/debug connector. The brief fixes the function, the power source, the single pushbutton, a floor of at least eight individually controllable RGB LEDs, the exposure of a small programming/debug connector, and the qualitative goals of being inexpensive and easy to assemble; it also states a preference for a two-layer board unless there is a compelling reason not to. Everything else is deliberately unfixed — the brief explicitly hands the MCU, the LED technology, the exact board shape, and the connector family to the design agent, and it names no form for either connector. This is a detail-1 brief, so nearly all architecture, part selection, rail design, mechanical definition and stackup detail are left to the design agent, and this repository intentionally records those as open decisions rather than pre-answering them.

> **This board has not been designed.** There is no schematic, no layout and no
> part selection here — only the brief, a reading of the brief, and the
> scaffolding a design run needs. That is the intended state of this repository,
> not a gap in it.

## What the brief fixes, and what it leaves open

The brief pins down 13 requirements and deliberately leaves
16 decisions to whoever designs the board. The `Source` column says
which is which: `brief` is quoted from [BRIEF.md](BRIEF.md), `metadata` comes
from the benchmark catalogue, and `open` means the brief does not fix it.

| Aspect | Value | Source |
|---|---|---|
| Category | simple-digital | metadata |
| Difficulty | 1 of 5 | metadata |
| Brief detail | 1 of 5 (low-detail brief; most architecture left open) | metadata |
| Likely layer count | 2 | metadata |
| Primary stressors | basic component selection, simple placement/routing, LED current limiting, connector access | metadata |
| Function and power source | A small USB-powered status beacon board | brief |
| Controller | A microcontroller (specific device not named by the brief) | brief |
| User input | One pushbutton | brief |
| Indicators | At least eight individually controllable RGB LEDs (a floor, with no upper bound stated) | brief |
| Programming/debug access | A small programming/debug connector must be exposed; the brief names no family, form or pinout | brief |
| Cost and assembly posture | Inexpensive and easy to assemble | brief |
| Layer count preference | Two layers preferred, deviation allowed only with a compelling reason | brief |
| MCU, LED technology, board shape, connector family | Explicitly delegated to the design agent by the brief | brief |
| Status of stated requirements | Stated requirements are authoritative; open choices are to be decided and documented, not invented into requirements | brief |
| Rails, regulation, and power budget | Not fixed by the brief — design agent's choice | open |

The full split, with the verbatim brief text substantiating every fixed
requirement, is in [board/requirements.md](board/requirements.md) and
machine-readably in [board/requirements.json](board/requirements.json).

**Missing details are design freedom, not permission to fabricate unstated user
requirements.** A choice the brief left open is recorded as a decision, with its
reasoning — never promoted into a requirement.

## Benchmark position

| | |
|---|---|
| Benchmark id | 1 of 32 |
| Category | simple-digital |
| Difficulty | 1 / 5 |
| Brief detail | 1 / 5 |
| Likely layer count | 2 |
| Primary stressors | basic component selection, simple placement/routing, LED current limiting, connector access |

At difficulty 1/5 and detail 1/5 in the `simple-digital` category, this board tests whether a design agent can execute competently with almost no specification handed to it — the metadata's stressors are basic component selection, simple placement/routing, LED current limiting, and connector access. The interesting question is not whether the circuit is hard, but whether the agent makes and justifies its own choices (MCU, LED technology, shape, connector family) instead of fabricating requirements the brief never stated. Two of those stressors — LED current limiting and connector access — are where the missing detail bites hardest: with no brightness, current, environment or mechanical context stated, the per-LED current, the total the board draws from USB with the whole array lit, and the physical usability of the connectors all have to be derived and shown rather than asserted.

This repository is one of thirty-two. The suite, the protocol and the results
live in [PCBA_AutoDesignAndTest_Bench](https://github.com/pentolope/PCBA_AutoDesignAndTest_Bench).

## Repository layout

| Path | Contents |
|---|---|
| `BRIEF.md` | the supplied brief — authoritative, preserved byte for byte, never edited |
| `board/requirements.md` | what the brief fixes, what it leaves open, and where decisions get recorded |
| `board/requirements.json` | the same split, machine-readable, each fixed requirement bound to brief text |
| `board/manifest.template.json` | the toolkit's minimum manifest, pre-filled for this board |
| `board/toolchain.json` | where this board's build finds KiCad and the router |
| `benchmark/metadata.json` | the supplied catalogue entry — category, difficulty, detail, stressors |
| `docs/architecture.md` | the decisions this board must make, as questions, unanswered |
| `docs/sources.md` | the classes of evidence the design will have to cite |
| `docs/status.md` | what exists, what does not, and what is deliberately absent |
| `candidates/` | disposable search output, ignored by Git |
| `tooling/PCBA_AutoDesignAndTest` | the shared verification/routing/release toolkit, as a pinned submodule |

## Getting the repository

The toolkit is a submodule and carries KiCad Routing Tools as a submodule of its
own, so clone recursively:

```bash
git clone --recursive https://github.com/pentolope/PCBA_StatusBeacon.git
```

```bash
git submodule update --init --recursive
```

## Designing the board

Generic verification, routing and release logic is **not** written here. It is
consumed from `tooling/PCBA_AutoDesignAndTest`, which is board-agnostic by
construction and must stay that way; this repository owns the board and nothing
else. Start from
[the toolkit's onboarding guide](tooling/PCBA_AutoDesignAndTest/examples/onboarding.md),
and see [CLAUDE.md](CLAUDE.md) for the rules a design run works under.

```bash
python3 tooling/PCBA_AutoDesignAndTest/run.py preflight
```

## Brief integrity

`BRIEF.md` SHA-256 `57889bbb86eda40bff9fa7fda22a93a18370e8318bfdb673a84f301cc4c06788`

Every quotation in `board/requirements.json` is bound to those exact bytes. If
the brief ever changes, the bindings are stale by construction — which is the
point of recording the digest.

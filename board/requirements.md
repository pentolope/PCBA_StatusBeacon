# Requirements — Status Beacon Controller

Two lists. The difference between them is the whole point of this file.

A **fixed requirement** is something [BRIEF.md](../BRIEF.md) asks for. Each one
below quotes the brief text that substantiates it; if a statement cannot be
quoted, it is not a requirement here. An **open decision** is a choice the brief
deliberately left to whoever designs this board.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Promoting a decision into a requirement is the failure this file exists to
prevent. Record a choice under the decision it answers, with the reasoning that
made it — never by adding it to the list above.

Bound to `BRIEF.md` SHA-256 `57889bbb86eda40bff9fa7fda22a93a18370e8318bfdb673a84f301cc4c06788`.

## Fixed by the brief

### REQ-01 — The board is a status beacon board and is powered from USB.

Brief text:

> Design a small USB-powered status beacon board with a microcontroller

### REQ-02 — The board is small. (The brief states the size goal qualitatively only; no dimension is given.)

Brief text:

> Design a small USB-powered status beacon board with a microcontroller

### REQ-03 — The board carries a microcontroller. The brief names no specific device, family, or vendor.

Brief text:

> a microcontroller, one pushbutton, and at least eight individually controllable RGB LEDs

### REQ-04 — The board carries one pushbutton.

Brief text:

> one pushbutton, and at least eight individually controllable RGB LEDs

### REQ-05 — The board carries at least eight RGB LEDs, and each must be individually controllable. Eight is a floor, not a fixed count; the brief sets no upper bound.

Brief text:

> at least eight individually controllable RGB LEDs. It should be inexpensive

### REQ-06 — The board must be inexpensive.

Brief text:

> It should be inexpensive, easy to assemble, and expose a small programming/debug connector.

### REQ-07 — The board must be easy to assemble.

Brief text:

> It should be inexpensive, easy to assemble, and expose a small programming/debug connector.

### REQ-08 — The board must expose a small programming/debug connector. The brief fixes neither its family, nor its pinout, nor its physical form.

Brief text:

> easy to assemble, and expose a small programming/debug connector

### REQ-09 — The MCU, the LED technology, the exact board shape, and the connector family are the design agent's to choose — the brief assigns these choices rather than leaving them accidentally unstated.

Brief text:

> Choose the MCU, LED technology, exact board shape, and connector family yourself.

### REQ-10 — A two-layer board is preferred; any other layer count must be justified by a compelling reason recorded in the design.

Brief text:

> Prefer a two-layer board unless there is a compelling reason not to.

### REQ-11 — Open choices must be resolved with documented engineering decisions; hidden user requirements must not be invented.

Brief text:

> make and document reasonable engineering decisions rather than inventing hidden user requirements

### REQ-12 — This repository stays a consumer of the shared PCBA_AutoDesignAndTest toolkit; board-specific logic must not be pushed into the toolkit.

Brief text:

> The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

### REQ-13 — The requirements the brief does state are authoritative and bind the design; they may not be relaxed, traded away, or overridden by the design agent's own preferences, and the open/fixed boundary is set by the brief itself.

Brief text:

> Treat stated requirements as authoritative; where the brief leaves choices open

## Open — the design agent decides

### OPEN-01 — Which microcontroller (family, part, package, memory, peripheral set) drives the board.

The brief says only 'a microcontroller' and then explicitly tells the design agent to choose the MCU itself.

*Decision:* **not yet made.**

### OPEN-02 — Which LED technology implements 'individually controllable RGB' — the choice between an addressable/serial-protocol LED, discrete RGB LEDs with per-channel drive, a driver IC, or a multiplexed scheme.

The brief requires individual controllability and at least eight units but explicitly delegates 'LED technology' to the design agent.

*Decision:* **not yet made.**

### OPEN-03 — How many RGB LEDs are actually placed, and their geometric arrangement on the board.

The brief states a floor ('at least eight') and no upper bound, and fixes no arrangement.

*Decision:* **not yet made.**

### OPEN-04 — The current-limiting strategy for the LEDs — per-channel resistors, a constant-current driver, integrated current control, or firmware-side duty limiting — and the target per-LED current.

The brief states no brightness, current, or drive requirement; 'LED current limiting' appears only as a benchmark stressor, not as a specified solution.

*Decision:* **not yet made.**

### OPEN-05 — The USB interface: its physical form (board-mounted socket, board-edge plug, captive cable, or bare pads), which USB connector type within that form, and whether USB is used for data as well as power.

The brief fixes only that the board is USB-powered and tells the design agent to choose the connector family; it names no connector form.

*Decision:* **not yet made.**

### OPEN-06 — The programming/debug connector family, pin count, pitch, footprint, and pinout, and whether it is a header, pads, or a keyed connector.

The brief requires 'a small programming/debug connector' but names no family, and explicitly assigns connector-family choice to the design agent.

*Decision:* **not yet made.**

### OPEN-07 — The power architecture downstream of USB: whether any regulator is used, what rail(s) exist, their voltages, and the total current budget against what the USB source can supply.

The brief is silent on rails, regulation, and power budget.

*Decision:* **not yet made.**

### OPEN-08 — The board outline, dimensions, and any mounting or mechanical features.

The brief says 'small' and explicitly leaves 'exact board shape' to the design agent; no dimension, mounting scheme, or enclosure is mentioned.

*Decision:* **not yet made.**

### OPEN-09 — The stackup: whether to stay at two layers as preferred, and if not, what compelling reason justifies more, plus copper weight, board thickness, and finish.

The brief expresses a two-layer preference with an escape clause but fixes no stackup details.

*Decision:* **not yet made.**

### OPEN-10 — Pushbutton type, footprint, actuation force/travel, and whether debounce is handled in hardware, firmware, or both.

The brief specifies only that there is one pushbutton.

*Decision:* **not yet made.**

### OPEN-11 — Protection strategy for the USB port and any exposed connector — ESD, reverse-polarity, overcurrent — and whether any is warranted at all.

The brief mentions no environment, no protection requirement, and no compliance target; 'connector access' is listed as a stressor, not as a specified protection scheme.

*Decision:* **not yet made.**

### OPEN-12 — Optical treatment of the LEDs: diffusion, spacing, viewing angle, top- versus side-emitting placement, and whether light bleed between channels matters.

The brief states the beacon function but no optical, brightness, or visibility requirement.

*Decision:* **not yet made.**

### OPEN-13 — The assembly process assumed: single-sided versus double-sided placement, all-SMT versus mixed technology, and which choices actually deliver 'easy to assemble'.

The brief asserts the goal but defines no process, panel, or manufacturer constraint.

*Decision:* **not yet made.**

### OPEN-14 — What 'inexpensive' means in measurable terms — the cost target, the quantity it is evaluated at, and the fabricator/assembler assumed.

The brief gives no budget, volume, or vendor.

*Decision:* **not yet made.**

### OPEN-15 — Firmware/behavioural definition: what the beacon indicates, what the pushbutton does, and whether any host interface or configuration exists.

The brief describes hardware content only and states no behaviour or protocol.

*Decision:* **not yet made.**

### OPEN-16 — Test and bring-up provisions: test points, boot/reset strapping access, and how a populated board is verified.

The brief requires only that a programming/debug connector be exposed, and says nothing about test coverage.

*Decision:* **not yet made.**

## Where a decision gets recorded

1. Answer it under its `OPEN-nn` heading above, with the reasoning and the
   evidence that made the choice.
2. Set `chosen` and `rationale` on the matching entry in
   [requirements.json](requirements.json).
3. Cite the datasheet or standard in [docs/sources.md](../docs/sources.md).

A choice recorded this way stays visibly a choice. That is what lets a later
reader tell this board's engineering apart from its brief.

## Where this board is most likely to be faked

Places where a design run would be tempted to assert something it cannot
substantiate:

- The brief is detail 1/5, so the strongest temptation is to invent requirements it never stated — a supply voltage, an enclosure, a board size in millimetres, a brightness target, a connector form, or a named MCU. Every such number must be recorded as the design agent's own decision with its own justification, never as a brief requirement.
- 'LED current limiting' is a listed stressor, not a chosen solution. A design that drops in series resistors without deriving the value from the selected LED's forward voltage and the actual rail — or that specifies a driver IC without comparing it to the simpler option — has skipped the thing this board is testing.
- The all-LEDs-on current is the one number most likely to be asserted rather than computed. At least eight RGB units means at least twenty-four emitters; a design that never totals that against what USB can supply has an unverified power budget.
- 'Individually controllable' is easy to claim and easy to violate. A multiplexed or shared-drive scheme may not deliver true simultaneous independent control of all channels; the design must show how the chosen topology satisfies the requirement, not just assert it.
- 'Inexpensive' and 'easy to assemble' are stated requirements with no metric attached. They are likely to be claimed in prose and never substantiated with a BOM total, a quantity, or an assembly-process argument.
- The two-layer preference has an escape clause, which invites an unjustified jump to four layers for convenience. Any deviation needs a compelling reason recorded against the brief's exact wording.
- The programming/debug connector can be placed to satisfy a netlist while being physically unusable — fouled by the USB cable, blocked by LEDs, or too cramped for a real probe. Connector access is an explicit stressor here, and the brief fixes neither connector's family nor its physical form.
- Protection (ESD, overcurrent, reverse insertion) is unstated in the brief. Both adding it and omitting it are defensible; asserting that the brief required it, or silently omitting it with no reasoning, are not.

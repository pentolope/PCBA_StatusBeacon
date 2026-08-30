# Architecture — Status Beacon Controller

**A worksheet, not a design.** Every line below is a question this board has to
answer, and none of them is answered here. Nothing in this file is a
recommendation, and the order of the sections carries no preference.

The questions were derived from [the brief](../BRIEF.md) and from what this
board is meant to stress in the benchmark:

- basic component selection
- simple placement/routing
- LED current limiting
- connector access

Those are the places where a wrong answer shows up in copper.

Answer them in this file as the design is made, each answer carrying the
evidence that supports it, and record the corresponding choice against its
`OPEN-nn` entry in [board/requirements.md](../board/requirements.md). An answer
without evidence is a guess wearing a document's clothes — and this benchmark is
allowed to refuse an unsupported claim rather than invent one.

## USB power entry and budget

- Which USB connector type is used, and what does that choice imply about the current the board may legally draw before any negotiation?
- What is the worst-case current with all RGB LEDs at full output simultaneously, and does that fit inside the assumed USB source capability?
- If the all-on case exceeds the budget, is the limit enforced in hardware, in firmware, or by specifying a lower per-LED current — and where is that limit recorded?
- What decoupling does the design provide, and is it sized against the current the LED array draws and switches rather than against the MCU alone?
- Is any inrush behaviour at plug-in significant enough to need addressing?
- Does the board rely on USB data lines at all, or is the port power-only — and how is that signalled to a user who plugs it into a host?

## Microcontroller selection and support

- What peripheral, timing and memory capabilities does the chosen LED drive scheme actually demand of the MCU, and does the selected part meet them with margin?
- Does the MCU run directly from the USB-derived rail, or is a regulator required, and what is the evidence for the chosen rail voltage?
- What clock source is required by the LED protocol timing and by any USB function, and is an external crystal/oscillator needed?
- What reset, boot-mode and strapping pins exist on the chosen part, and are they all reachable during bring-up?
- How many GPIO are needed in the worst-case drive topology, and does the chosen package expose them?
- Is the package choice consistent with the 'easy to assemble' requirement?

## RGB LED array: technology, topology and current limiting

- Which LED technology is chosen, and how does it deliver individual controllability for at least eight RGB units?
- What is the drive topology — serial/addressable chain, per-channel GPIO/PWM, dedicated driver IC, or multiplexing — and what does it cost in pins, parts and board area?
- How is LED current limited in the chosen topology, and which forward-voltage and forward-current numbers from the chosen LED's datasheet does that limit follow from?
- Does the limiting calculation account for the actual rail voltage, LED colour-dependent forward voltage, and tolerance spread?
- What is the power dissipated in the limiting elements and in the LEDs themselves, and does anything need thermal attention?
- If a serial protocol is used, what are its timing requirements, and does the routing and MCU service loop meet them for the full chain length?
- How many LEDs beyond the required eight, if any, and why?

## Pushbutton input

- What button style and footprint is selected, and how does it survive repeated actuation given the board's likely handling?
- Is the input pulled up/down externally or by the MCU's internal resistor, and is that documented?
- Is debounce handled in hardware, in firmware, or both, and what bounce time does the chosen switch's datasheet support?
- Does the button share a pin with any boot/strap function, and if so what happens if it is held at power-up?
- Is the button reachable once the board is mounted or placed in whatever way a beacon is used?

## Programming and debug connector access

- Which connector family and pinout is chosen, and what programming/debug interface does the selected MCU actually require?
- Is the connector small, as the brief requires, and what is the evidence that the chosen footprint qualifies?
- Is the connector physically accessible with the board in its intended orientation, without a probe fouling the LEDs or the USB connection?
- Is the connector keyed or otherwise protected against reversed insertion, or is orientation documented on the silkscreen?
- Which signals does the chosen debug interface actually require at the connector — including whether it needs reset, a ground reference, or target power — and is a published reference for that pinout cited and followed?
- Should the debug interface be a populated connector or unpopulated pads, given the cost and assembly goals?

## Board outline, placement and optical layout

- What outline and dimensions are chosen, and what drives them — the LED arrangement, the connector edges, or something else?
- How are the LEDs arranged so the board reads as a beacon, and does that arrangement constrain the routing?
- Are the USB and debug connectors placed so that both can be used at once and neither overhangs the outline improperly?
- Are mounting holes or mechanical features needed, and if none, what is the justification?
- Is there any keepout required around connector bodies, and around any LED that must not be shadowed?
- Does the placement keep the board single-sided for assembly if that was the chosen cost strategy?

## Stackup and routing plan

- Does the design stay at the preferred two layers, and if not, what is the compelling reason, stated explicitly?
- On two layers, what ground scheme is chosen and on what grounds, and what return path does it give the LED drive currents?
- What trace width is required for the worst-case LED array current, and is that derived from a current-capacity reference rather than assumed?
- Does the chosen fabricator's minimum trace/space and drill capability support the selected packages and pitches?
- Is the LED chain or drive routing length consistent with any timing or signal-integrity limits the chosen technology imposes?
- Where does the switching noise from the LED array flow, and does it couple into the MCU or the debug lines?

## Robustness at the connectors

- What handling does the USB connection on a bare beacon board actually see, and does the chosen USB connector form have adequate mechanical retention or anchoring for it?
- Is any ESD or overcurrent protection warranted on the exposed port, and what is the argument either way given no stated environment?
- If protection is added, what does it cost in parts and area against the 'inexpensive' requirement?
- How does the board behave if the debug connector is attached while USB power is present?
- Is reverse or miswired debug-connector insertion survivable, or is it simply documented as a user responsibility?

## Cost and assembly

- What quantity and vendor assumption defines 'inexpensive' for this board, and is the BOM cost actually totalled against it?
- Are components restricted to a single assembly side, and is every part in the assembler's standard/basic library where that matters for cost?
- Is the part count minimised where a topology choice allows it — for example, has the current-limiting approach been compared on part count as well as accuracy?
- Are all chosen packages placeable by standard pick-and-place, with no hand-soldered exceptions?
- Does anything in the design force a more expensive fabrication option (extra layers, tighter drill, special finish), and is it justified?

## Bring-up, test and verification

- What is the minimum sequence to prove a freshly assembled board is alive, and does the debug connector alone support it?
- Which nets need test points to diagnose a dead board, and are they placed?
- How is each of the eight-plus RGB channels verified as individually controllable rather than just collectively lit?
- How is the actual per-LED current measured against the design intent on a real board?
- What is the pass/fail criterion for the pushbutton, including debounce behaviour?
- Is there a defined failure mode if the LED array is driven at full output for an extended period?

## Answers still owed

All of them. See [status.md](status.md).

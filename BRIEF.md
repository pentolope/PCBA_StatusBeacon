# PCBA_StatusBeacon — Status Beacon Controller
## Design brief

Design a small USB-powered status beacon board with a microcontroller, one pushbutton, and at least eight individually controllable RGB LEDs. It should be inexpensive, easy to assemble, and expose a small programming/debug connector. Choose the MCU, LED technology, exact board shape, and connector family yourself. Prefer a two-layer board unless there is a compelling reason not to.

## Functional requirements

- Each LED's red, green and blue elements shall be settable independently, and updating one LED shall not disturb the others.
- The pushbutton shall be the only user control; press and release shall reach the MCU as single debounced events.
- On USB power alone, with no host software, the board shall reach a defined LED state.

## LED array and drive

- Drive signals shall meet the receiving device's input thresholds across the operating range, including any rail difference.
- Peak LED current shall be bounded by the drive circuit or by one documented firmware limit, shall repeat across assemblies without rework, and shall not produce visible flicker.

## Power and current budget

- Worst-case current, all LEDs at maximum with the MCU active, shall be calculated, measured at bring-up, and within what the board may draw from the port it declares.
- Operation shall hold over the full VBUS range the connector and cable permit at that load, with input capacitance inside the USB inrush limit and any lower rail within its temperature limits.

## Interfaces and debug connector

- The USB receptacle shall be mechanically retained so mating forces are not carried by signal joints alone; a Type-C sink shall present its class's CC terminations.
- The debug connector shall program and halt the chosen MCU in circuit on a blank or bricked device, be polarised or pin-1 marked, and be unnecessary in normal use.

## Mechanical, placement and assembly

- Two copper layers unless a documented constraint forces more, with continuous ground reference under the MCU and LED clock and data routing.
- LED positions shall form a deliberate, repeatable arrangement, and the button shall be operable without touching the LEDs or connector.
- Assembly shall need no more than stencil print, single-side placement and one reflow pass.

## Protection and bring-up

- Exposed USB contacts and the pushbutton shall have ESD protection to board ground; hot-plug shall not damage or latch up the board, and no signal shall be driven into an unpowered device.
- VBUS, ground and every LED drive signal shall be probeable when assembled, and total supply current measurable without cutting a trace.

## Open choices

- MCU, LED technology and drive topology, and per-channel resolution: on/off, or a stated modulation depth.
- USB receptacle and debug connector families; board outline and LED geometry; whether the board enumerates or takes power only.

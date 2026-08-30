# PCBA_StatusBeacon — Status Beacon Controller

**Benchmark ID:** 01  
**Difficulty:** 1/5  
**Brief detail:** 1/5  
**Category:** simple-digital  
**Likely layer count:** 2  
**Primary stressors:** basic component selection, simple placement/routing, LED current limiting, connector access

## Design brief

Design a small USB-powered status beacon board with a microcontroller, one pushbutton, and at least eight individually controllable RGB LEDs. It should be inexpensive, easy to assemble, and expose a small programming/debug connector. Choose the MCU, LED technology, exact board shape, and connector family yourself. Prefer a two-layer board unless there is a compelling reason not to.

## Benchmark intent

This brief is intentionally one member of a heterogeneous PCBA-autodesign benchmark. Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements. The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

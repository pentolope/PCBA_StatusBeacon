# Sources — Status Beacon Controller

The evidence this board's design will have to cite. **Classes of document, not
documents:** the specific parts are not chosen yet, so naming a datasheet here
would be choosing one.

A number that reaches the board carries its provenance: source, document id or
URL, retrieval date, units, and the condition it applies under. A number without
that is not evidence, and no live network lookup may change a validation or
release result.

| Kind of source | What the design needs from it |
|---|---|
| MCU datasheet and reference manual for the selected part | Pin capabilities, GPIO drive strength, peripheral/timer resources for the LED drive scheme, supply-voltage range, package and boot/strap behaviour — none of which can be assumed before the MCU is chosen. |
| RGB LED (or addressable LED) datasheet for the selected device | Forward voltage per colour, forward-current rating, protocol timing if addressable, viewing angle and thermal limits — these set the current-limiting calculation and the drive timing. |
| LED driver or current-source IC datasheet, if that topology is selected | Channel count, current-setting method, headroom and dissipation limits needed to justify the drive topology against a resistor-based alternative. |
| USB specification (the revision matching the chosen connector and mode) | The current a device may draw before enumeration or negotiation, which bounds the whole LED power budget; also connector mechanical and pinout definitions. |
| USB connector datasheet and recommended land pattern for whichever connector form is chosen | Mechanical retention, mating cycles, footprint and keepout for a port that will be handled repeatedly — the applicable document differs for a board-mounted socket, a board-edge plug, or a captive cable, so it follows the connector decision. |
| Debug/programming interface specification for the selected MCU's tool ecosystem | The signal set, connector pinout and voltage expectations that make the exposed debug connector actually usable with a real programmer. |
| Debug/programming connector datasheet and footprint | Pitch, body size and keying, which the 'small' requirement and the access questions turn on. |
| Tactile switch datasheet | Bounce time, actuation force, mating/actuation life and footprint for the single pushbutton. |
| PCB fabricator capability page for the chosen layer count | Minimum trace/space, drill, annular ring, finish and panel rules that constrain the routing and the outline. |
| Assembly-house part library and pricing data | Substantiating 'inexpensive' and 'easy to assemble' with actual availability, part-library tier and per-board cost at a stated quantity. |
| PCB current-capacity / trace-width reference (e.g. IPC-2152-class data) | Sizing the LED array power traces from evidence rather than habit, especially on a two-layer board with limited copper. |
| Passive component datasheets for the current-limiting and decoupling elements | Tolerance, temperature coefficient and power rating for whatever elements set LED current, and voltage rating/derating for the bulk capacitors. |

## Recording a source, once one is chosen

Replace the class with the actual document — manufacturer, part number, revision
and date — and state the fact taken from it, in the units the document uses.
Keep the class row: it says why the document was needed.

JLCPCB-wide process limits are **not** recorded here. They live in the toolkit's
`profiles/jlcpcb/`, with their own provenance; this board records only its own
tighter targets and its own selected options. A limit copied into two places is
a rival threshold, and the toolkit has a gate that says so.

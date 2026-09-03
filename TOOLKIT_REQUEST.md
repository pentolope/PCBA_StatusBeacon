# Toolkit requests from 01_PCBA_StatusBeacon

Written after taking this board from brief to `RELEASE READY`. Every item is
something that either blocked the board, cost cycles, or is still preventing an
honest release under `AUTONOMOUS_PCBA_AGENT.md`.

Each request states the shape it wants — manifest key, gate ID, or API — so it
converts into schema and code rather than staying prose. Nothing here asks the
toolkit to learn anything about this board: where a board-specific value is
needed, the request is for the manifest key that carries it.

Priorities: **P1** blocks a correct release. **P2** cost real cycles on this
board and will cost them again. **P3** improves evidence quality.

---

## P1 — Criteria §32 requires that the toolkit cannot express

### 1. A policy for unresolved and unsupported claims

§32 requires that *"unresolved unsupported claims are either explicitly
permitted or blocking according to board policy"*. There is no mechanism for
this. This board carries 11 `UNKNOWN` claims — the WS2812B's DOUT drive levels,
which its datasheet simply does not specify — and 4 more that are labelled
estimates. Nothing in the manifest can say whether those permit a release or
block it, so the criterion is unmet no matter what the board does.

Requested: a `claims` manifest block and a `CLAIM.POLICY` gate.

```json
"claims": {
  "source": "generated/rules.json",
  "unsupported": {
    "default": "blocking",
    "permitted": [
      {"id": "logic_high_margin", "scope": "D*.2->D*.4",
       "because": "the receiver's DOUT levels are unspecified by its vendor",
       "accepted_by": "…", "review_by": "2027-03-01"}
    ]
  },
  "approximate": {"default": "permitted-with-label"}
}
```

The gate reads the board's own claim records (shape already fixed by
`pcbqa/claim.py`), classifies every non-PASS verdict, and fails on any that
policy does not explicitly permit. A permitted entry that no longer matches a
live claim should also fail, so stale waivers cannot accumulate.

This is the single change that most improves release honesty: it converts
"there are some UNKNOWNs" into an enumerated, owned, expiring list.

### 2. A policy state on every result

§30 asks that a result carry enough policy for the agent to know what it
permits, with states like `analysis-only`, `requires-additional-evidence`,
`fabrication-ready`, `release-ready`. Today `release-check` is binary: READY or
BLOCKED. That binary told me this board was releasable when several §32
criteria were unmet, because it reports only on the checks the board opted
into.

Requested: `validate` and `release-check` emit a policy state derived from
which gates ran, which were `NOT_APPLICABLE`, and what the claim policy says.
A board that declares no thermal block and no claim policy should not be able
to reach `release-ready` — it should land on `requires-additional-evidence`.

### 3. Non-applicability must be visible in the verdict

13 of this board's 36 gates report `NOT_APPLICABLE`, each with a reason, which
is the right behaviour. But the release verdict weights them the same as if
they did not exist. A board can therefore reach READY by declining to declare
the blocks that would have tested it hardest.

Requested: `release_profile` gains a `required_domains` list. Declining a
domain becomes an explicit act recorded in the manifest, not a silence.

---

## P1 — Verification domains the specification names and the toolkit lacks

### 4. Thermal (§24)

There is no thermal module at all. §24 asks for component dissipation, copper
spreading, junction-to-board paths, ambient and airflow assumptions, and
regulator thermal margin. I built `design/thermal.py` in this board because
nothing existed, and it found the board's most significant open issue: at full
brightness the regulator dissipates 199 mW against 172 mW of derated
allowance, so the firmware brightness limit is load-bearing for a *thermal*
rating and not only the USB current budget.

None of that is board-specific in principle. Requested: `pcbqa/thermal.py` plus
a `thermal` manifest block and `THERMAL.*` gates.

```json
"thermal": {
  "ambient_max_c": 40.0,
  "boundary": {"orientation": "horizontal", "airflow": "none",
               "enclosure": "none", "emissivity": 0.90},
  "outline_from": "board",
  "dissipation": {
    "sources": [{"refs": "D*", "model": "rail_current",
                 "current_from": "components/parameters.json"}]
  },
  "limits": {"per_part_operating_max_c": "components/parameters.json"}
}
```

Gates: `THERMAL.DISSIPATION` (every source attributed, nothing unaccounted),
`THERMAL.PART_RATINGS` (each part inside its declared operating limit),
`THERMAL.DERATING` (dissipation against package rating derated to the local
temperature). The board-average rise model I wrote — natural convection plus
radiation over the real outline area, solved iteratively — is about 60 lines
and generalises directly; the outline area should come from `Edge.Cuts`, not a
declared number.

Two properties matter more than the model's sophistication. Claims that depend
on the estimate must come out `APPROXIMATE` carrying their boundary conditions,
so their verdicts are `UNKNOWN` — §24 is explicit that a simple estimate must
be labelled as one. And a part whose datasheet gives no θJA (the WS2812B gives
none) must yield `UNKNOWN`, never an invented junction temperature.

### 5. Power integrity (§23)

Nothing exists. The one piece that does — `extract.path_resistance` — **refuses
on any net carrying filled zone copper**, which is exactly the set of nets whose
IR drop matters. On this board I could extract a 6.5 mm signal trace and not the
power rail.

Requested, in rough order of value:

- **plane spreading resistance**, so `+5V` and `GND` become extractable and
  source-to-load DC drop is answerable on real boards;
- **decoupling loop inductance** per bypass capacitor, from the actual
  capacitor-to-via-to-plane geometry;
- **PDN impedance versus frequency**, which needs the AC analysis in item 9;
- `POWER.IR_DROP` and `POWER.DECOUPLING` gates over a `power_integrity`
  manifest block declaring rails, loads and limits.

---

## P2 — Things that cost cycles on this board

### 6. Part lifecycle and availability against a frozen snapshot

The LED I selected, `WS2812B-B/T`, is flagged **discontinued** by the
fabricator. Nothing caught it. I found it by chance while researching an
unrelated question, several design iterations after committing to it.

Requested: a `lifecycle` manifest block naming a committed snapshot, and a
`BOM.LIFECYCLE` gate that fails on discontinued parts and warns on low stock or
single-source risk. This must follow the existing catalogue discipline exactly:
a `fab refresh`-style command fetches and writes a reviewable snapshot, the
commit is the approval, and **no live lookup may change a verdict**.

Cheap to build, and it would have saved an entire part-selection cycle.

### 7. Placement checks before routing

Replacing a diode with a SOT-23-5 regulator produced a courtyard overlap with
its input capacitor. I discovered it only after the router had burned three
candidate attempts and the acceptance gates rejected all three — several
minutes per cycle to learn something a geometry check answers in milliseconds.

Requested: `PLACEMENT.COURTYARD` and `PLACEMENT.EDGE_CLEARANCE` gates that run
on the placed board, plus a documented convention that they belong in the
routing acceptance set. DRC catches this eventually, but only after routing,
which is precisely the expensive path.

### 8. Gates should declare what they judge

Candidate-based routing has to judge the *design*, because the release
artifacts are generated from a board the search has not finished choosing. I
added `validate --only=<ids>` for this, and the board now maintains
`routing.acceptance_gates` — a hand-written list of 15 gate IDs that silently
goes stale whenever a gate is added.

Requested: each gate declares a class (`design`, `release-artifact`,
`fixture`), and `validate --only=design` selects by class. The board's list
disappears and cannot rot.

### 9. Simulation coverage

`pcbqa/sim/` is good, and after this board it is reachable. Remaining gaps, all
hit here:

- **Current sources.** The scenario schema has no `isource_dc` or
  `isource_pulse`. An LED array is a current sink; I had to model a switched
  load as a voltage source pulling through a resistor, which is a workaround
  for a missing primitive.
- **AC analysis.** No `.ac`, so no PSRR, no PDN impedance, no filter response.
  Needs `ac` in `_ANALYSIS_KEYS` and `ac_magnitude` / `ac_phase` measurements.
- **Current and differential measurements.** Only node voltages exist.
- **A regulator model class.** `model_registry` handles subcircuits, but a
  regulator's behaviour is its output tolerance, dropout and load regulation.
  Those are the numbers a rail claim depends on, and there is no shape for them.
- **DC sweep.** Bias points across a range currently require one scenario per
  point.

### 10. A netlist-level topology API

`connectivity.NetGraph` works on the board. Nothing works on the *netlist*, so
I wrote graph walks in the board twice — "which parts bridge these two nets"
and "which nets are joined through series passives" — and **both were wrong the
moment the topology changed**. Replacing a 0 Ω link with a diode broke the
first; replacing the diode with a regulator broke both, because each had
quietly assumed a two-terminal bridge and a shared VBUS/+5V domain.

Requested: `pcbqa/netlist_topology.py` with `bridges(net_a, net_b)`,
`reachable_through(net, kinds)` and `pins_on(net)`. Boards asking topology
questions of a static list is exactly how a board-specific assumption gets
baked into a rule.

---

## P3 — Evidence quality

### 11. Datasheet graph digitisation

I traced curves out of datasheet plots three times by hand — pixel-scanning the
rendered PDF, calibrating against gridlines, rejecting the axis labels and text
that the tracer picked up as data. It was the single most repetitive task in
this board, and the result is real evidence: the 1N5819WS analysis rests
entirely on a digitised typical curve, because the ratings table gives forward
voltage at only two currents.

Requested: `pcbqa/digitize.py` taking a page, a crop and axis calibration
(linear or log, two reference points per axis), returning traced series with a
**stated coordinate uncertainty** derived from pixel pitch, plus the crop's
digest so the trace is reproducible and bound to the frozen document.

### 12. Device parameter records with a knowledge level

`extract.physical_parameter` is exactly the right idea for physical inputs:
value, units, source type, digest, applicability. Device parameters have no
equivalent, and it matters. The regulator I fitted specifies dropout as
**typical only, at 100 mA and 200 mA**, with no maximum and no figure at the
current this board draws. The declared rail minimum therefore rests on an
extrapolation I chose, and nothing in the schema records that.

Requested: the same record shape for device parameters, carrying
`knowledge` (`exact` / `typical` / `bounded` / `unknown`), the conditions the
figure was measured at, and its validity range. A rule extrapolating beyond
that range should be forced to declare it, and any claim built on a
typical-only figure should be unable to come out `EXACT`.

This is the mechanism that would have made "the low rail rests on an
extrapolation" visible in the verdict instead of in my commit message.

### 13. Physical inputs reachable from validation

Resolving finished copper from the approved catalogue happens inside
`pcbqa.fabricators`, which validation may not import — correctly, since that
package can reach the network. So extraction inside a gate cannot resolve its
own physical inputs, and this board freezes them to a file instead.

That works, but the freeze is manual and can go stale against the catalogue
silently. Requested: a narrow read-only accessor over the *committed*
catalogue snapshot that carries no network capability and that validation may
import, or a `FAB.PHYSICAL_INPUTS_FRESH` gate that verifies a frozen set still
agrees with the committed catalogue.

### 14. Assembly and DFA (§25)

The toolkit checks BOM and CPL parity thoroughly, but §25 asks for a PCBA, not
a bare board. No check exists for paste aperture ratio, courtyard-to-courtyard
spacing for pick-and-place, thermal relief on large copper pads, or the
population/DNP consistency a fabricator actually reads.

---

## Already added while building this board

So these are not requested twice: `SIM.SCENARIOS`, `SIM.STAGE_COVERAGE` and
`SIM.MODEL_PROVENANCE`; `tran_min_voltage` and `tran_max_voltage` measurement
kinds; live path extraction into a scenario registry under a stable alias
(`extract.aliased`); `validate --only`; any-of `requires` tuples, which let
`fixture.attributes_file` gain the general name `closure.attributes_file`
without breaking a pinned consumer; `ROUTE.PROVENANCE`; `DRC.CONSTRAINT_FLOOR`;
mechanical pads excluded from connector position counts; and
`VIA.NATIVE_GERBER_AGREEMENT` requiring both keys it reads.

## Deliberately not requested

**Automatic remediation.** Several times the right move was to change the
design, and each time the toolkit's refusal to repair anything was correct. A
gate that fixed a board would have hidden the WS2812B datasheet contradiction,
the discontinued part, and the regulator's derating — all three surfaced
because something refused and made me look.

**A looser default.** Every gate that blocked this board blocked it for a real
reason. The two that needed changing were wrong in their *reasoning*, not their
strictness: they hardcoded a topology rather than deriving it.

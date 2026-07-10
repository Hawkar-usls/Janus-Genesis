# Architecture

## Product definition

PLA Janus Genesis is a **model-to-model transformer**. It does not start from an empty canvas. Its input is an existing mesh plus an engineering contract; its output is a ranked family of manufacturable candidates and evidence explaining every change.

## Pipeline

```text
INBOX
  -> Ingest
  -> Normalize units and mesh
  -> Protect interfaces
  -> Baseline metrics
  -> Candidate generation
  -> FEA
  -> FDM manufacturability filters
  -> Slicer estimate
  -> Pareto registry
  -> OUTBOX + REPORTS
```

## Modules

### Ingest

Loads STL/OBJ/PLY now. 3MF and STEP are planned. Original files are never overwritten.

### Model contract

Defines frozen geometry, loads, supports, clearances and objectives. A transformation is invalid if it violates protected geometry.

### Candidate generation

Planned strategies:

- topology removal inside an allowed design volume;
- stress-aligned ribs;
- variable-density lattice;
- shell/lattice hybrid;
- local thickening near fasteners;
- support-free orientation-aware mutations.

### Physics judge

The physics judge must use calibrated material data and multiple load cases. A neural model may propose candidates but may never replace the judge.

### Printability judge

Uses nozzle width, layer height, minimum walls, overhangs, bridges, trapped volumes and build volume.

### Pareto registry

Candidates are not collapsed into one dishonest score. Janus stores non-dominated solutions for mass, stiffness, safety factor, supports and print time.

## Evidence levels

- `mesh_repair_and_orientation_only`
- `simulation_candidate`
- `simulation_passed`
- `printed_tested`
- `calibrated_repeatable`

Only the last two levels may be described as physically validated.

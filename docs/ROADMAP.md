# Roadmap

## JG-0 — Foundation MVP

- [x] Clean repository identity
- [x] Folder-based model ingestion
- [x] Mesh metrics
- [x] Conservative repair
- [x] Orientation heuristic
- [x] Candidate and JSON report export
- [x] CI foundation
- [ ] 3MF import
- [ ] Visual before/after report

## JG-1 — Printability Judge

- [ ] Local wall-thickness map
- [ ] Overhang and bridge map
- [ ] Build-volume gate
- [ ] Nozzle-aware feature filter
- [ ] Bambu Studio/PrusaSlicer CLI estimate adapter
- [ ] Orientation Pareto candidates instead of one winner

## JG-2 — Geometry Contract

- [ ] Interactive protected-region marking
- [ ] Frozen mounting faces and holes
- [ ] Clearance volumes
- [ ] Design and keep-out volumes
- [ ] Automatic contract validation

## JG-3 — Physics Judge

- [ ] Gmsh meshing adapter
- [ ] CalculiX baseline solver
- [ ] Multiple load cases
- [ ] Displacement and stress reports
- [ ] FDM anisotropy model
- [ ] Creep and temperature warnings

## JG-4 — Transformer

- [ ] SIMP topology optimization
- [ ] Stress-aligned ribs
- [ ] Variable-density gyroid/TPMS
- [ ] Shell-to-lattice transitions
- [ ] Minimum feature and overhang filters

## JG-5 — Janus Evolution

- [ ] Candidate mutations
- [ ] Reproducible seeds
- [ ] Pareto archive
- [ ] Failure memory
- [ ] Surrogate model for faster proposals

## JG-6 — Physical Calibration

- [ ] Printable coupon generator
- [ ] Test rig protocol
- [ ] Per-spool material profile
- [ ] Update simulation from measured failures
- [ ] Repeatability gates

## Definition of success

For a selected model and declared loads, Janus should produce at least one candidate that:

1. preserves all protected interfaces;
2. passes the declared simulation gates;
3. uses less material than the baseline;
4. can be sliced with the declared printer profile;
5. survives a repeatable physical test.

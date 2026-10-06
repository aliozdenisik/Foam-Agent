# SIMULATION SERVICES

## OVERVIEW
Business logic and case filesystem boundaries; score 8: code ratio, module boundary, symbol density, and public symbols.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Generated-case planning | `plan.py` | Retrieval, case metadata, file subtasks |
| Imported-case planning | `plan.py:plan_imported_case` | Context-driven actions and target conflicts |
| Import materialization | `case_import.py` | Directory/ZIP discovery and immutable baseline |
| Generated path validation | `case_paths.py` | Shared containment checks |
| Output ownership | `output_safety.py` | Managed outputs and overwrite protection |
| Initial generation/rewrites | `input_writer.py` | Cross-file context and targeted repair |
| Mesh preparation | `mesh.py` | Standard mesh and custom mesh conversion |
| Local execution | `run_local.py` | Allrun and error collection |
| Slurm execution | `run_hpc.py` | Submission and locally available Slurm commands |
| Error diagnosis | `review.py` | Analysis and rewrite planning |
| Result rendering | `visualization.py` | PyVista outputs |

## CONVENTIONS
- Imported cases materialize into read-only `original/` and writable `work/`; reports remain separate.
- Route generated paths and output preparation through the shared safety modules.
- A clean imported case with `Allrun` and no explicit prompt/custom mesh skips file planning, not LLM resource loading or routing.
- Missing imported files may enter planning; missing non-inferable physical information produces planning failure.
- Explicit target conflicts become deterministic errors for the Reviewer repair path.
- Sequential generation shares previously generated file context; parallel generation intentionally does not.
- Repairs rewrite selected files rather than regenerating the entire case.
- Mesh repair can return directly to meshing or rewrite targeted files first.
- Repair convergence uses repeated error/case/request fingerprints as well as loop and graph limits.

## ANTI-PATTERNS
- Do not write into an imported baseline or bypass ZIP/path/output ownership checks.
- Do not mix native v2006 file conventions with Foundation generation references.
- Preserve visualization failure after successful simulation as `partial_success`; CLI still exits nonzero.
- Do not treat an empty `squeue` result as verified solver success: current HPC monitoring does not inspect `sacct` or the final exit code.
- Monitoring timeout can enter repair/resubmission while the original job remains active.

## VERIFICATION
- Case import and ownership regressions belong in `tests/test_case_import.py`.
- Translation gates are covered by `tests/test_esi_translator.py`.
- `tests/test_lid_driven_cavity_services.py` is a manual live simulation script, not an isolated unit-test suite.

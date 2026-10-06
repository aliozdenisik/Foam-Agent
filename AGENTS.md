# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-06
**Commit:** 18bdc1f
**Branch:** main

## OVERVIEW
Foam-Agent automates OpenFOAM CFD simulations from natural-language requirements or existing cases. Python, LangGraph/LangChain, FAISS retrieval, and FastMCP connect planning, generation, execution, and repair.

## STRUCTURE
```text
Foam-Agent/
|-- foambench_main.py    # Simulation CLI launcher
|-- init_database.py    # Target-specific corpus initialization
|-- src/                # Shared workflow and exposed MCP tools
|   |-- nodes/          # Thin graph adapters
|   |-- services/       # Simulation logic and case ownership
|   |-- mcp/            # Tool contracts and transport entry points
|   `-- translation/    # Legacy Foundation-to-ESI compatibility
|-- database/           # Target/model-scoped retrieval assets
|   |-- script/         # Corpus parsers and FAISS builders
|   `-- foamgpt/        # Separate dataset preparation utilities
|-- scripts/            # Target/corpus/container verification
|-- docker/             # Foundation and ESI runtime images
`-- tests/              # Regressions plus manual live simulations
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Workflow/provider/API changes | `src/AGENTS.md` | Import and orchestration contracts |
| Simulation or imported-case changes | `src/services/AGENTS.md` | Safety, generation, execution, repair |
| User-facing setup | `README.md`, `environment.yml` | Full Conda runtime environment |
| Packaging and console command | `pyproject.toml` | Registers `foamagent-mcp` |
| MCP usage | `src/mcp/README.md` | Tool boundaries and transport setup |
| Corpus rebuild | `init_database.py`, `database/script/` | Specify target and embedding configuration |
| Native ESI verification | `scripts/run_esi_docker_verify.sh` | Matching runtime/container required |
| Authentication regressions | `tests/test_codex_provider.py` | SDK boundary fakes and local fixtures |

## CODE MAP
LSP evidence; reference counts are observed results, not whole-project totals across bare/package import aliases.

| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| GraphState | TypedDict | `src/utils.py` | 18 | Workflow state contract |
| LLMService | Class | `src/utils.py` | 4 | Provider and structured-output interface |
| create_foam_agent_graph | Function | `src/main.py` | Not measured | Shared graph topology |
| Config | Dataclass | `src/config.py` | Not measured | Runtime configuration |
| import_case | Function | `src/services/case_import.py` | Not measured | Existing-case materialization |

## CONVENTIONS
- Foundation OpenFOAM v10 is the default; `FOAMAGENT_OPENFOAM_TARGET=esi-v2006` selects native ESI/OpenCFD v2006.
- `FOAMAGENT_OPENFOAM_FORK=esi` is a separate best-effort legacy translation path, not the native target.
- Native targets require matching sourced runtimes and isolated corpora under `database/<target>/`.
- Configuration environment overrides are explicit, not a generic mapping of all dataclass fields.
- Runtime embeddings default to Hugging Face/Qwen3-Embedding-0.6B; standalone builders default to OpenAI small.

## ANTI-PATTERNS (THIS PROJECT)
- Do not regenerate FAISS assets without a task-specific reason; hydrate Git LFS assets and select matching model indices first.
- Do not load one target's corpus or runtime for the other target.
- Preserve model/provider-scoped FAISS paths; native ESI currently has no prebuilt Qwen 8B indices.

## UNIQUE STYLES
- Graph nodes delegate simulation logic to services; graph routing is maintained separately.
- CLI failures and MCP result payloads expose termination reasons, including partial simulation success.
- Read subtree guidance before editing its domain; smaller directories inherit the nearest file.

## COMMANDS
```bash
conda env create -n FoamAgent -f environment.yml
conda activate FoamAgent
python foambench_main.py --output ./output --prompt_path ./user_requirement.txt
pytest tests/ -v
foamagent-mcp
python -m src.mcp.fastmcp_server --transport http --host 127.0.0.1 --port 7860
python -m src.codex_auth status
python -m src.codex_auth models
```

## NOTES
- Source OpenFOAM before simulation; native ESI requires `WM_PROJECT_VERSION=v2006`.
- Corpus builds should specify both `--embedding_provider` and `--embedding_model` explicitly.
- `init_database.py --database_path` takes a target directory; `Config.database_path` takes their parent.
- `tests/test_lid_driven_cavity_*.py` are live manual scripts; ordinary regressions use temporary files and fakes.
- The `integration` pytest marker identifies tests reading the full tutorial database.

# SOURCE KNOWLEDGE BASE

## OVERVIEW
Workflow orchestration, model adapters, and MCP contracts; score 11: file count, code ratio, package boundary, symbol density, and public symbols.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Graph topology | `main.py` | Shared generated/imported-case workflow |
| Conditional edges | `router_func.py` | Planner, mesh, runner, repair routes |
| State contract | `utils.py:GraphState` | Node-returned updates merge through LangGraph |
| Provider integration | `utils.py:LLMService` | Invocation and structured output |
| Codex runtime | `codex_provider.py` | Official SDK adapter |
| Authentication CLI | `codex_auth.py` | Status, model discovery, browser/device login |
| Configuration | `config.py` | Explicit environment overrides |
| Native target checks | `openfoam_target.py` | Runtime/corpus validation |
| MCP transport | `mcp/cli.py` | Console entry point |
| MCP tool schemas | `mcp/fastmcp_server.py` | Request/response models and adapters |
| Legacy translation | `translation/esi_translator.py` | Rules in `esi_translation_rules.json` |

## CONVENTIONS
- Existing modules use bare imports after entry-point path setup; preserve the established import arrangement.
- `services/__init__.py` constructs a global LLM client at import time.
- Configure the backend before importing service modules; an API key alone does not select its provider.
- Codex defaults to SDK model selection (`auto`), not the stale fixed-model defaults in some prose.
- Node returns carry state updates; nested configuration can also be mutated.
- `foamagent-mcp` defaults to stdio; the direct server module defaults to HTTP.
- Individual MCP tools are client-orchestrated; only `run_case` invokes the shared imported-case graph.
- Standalone MCP `run` is local-only; mesh/HPC routing belongs to the graph.
- Standalone MCP `review` uses fixed `simpleFoam`/`fluid`/`tutorial` retrieval metadata.
- `run_case` copies configuration before applying its per-invocation target.

## ANTI-PATTERNS
- Do not prepend `src/` in `mcp/cli.py`: local `mcp/` can shadow the installed MCP dependency.
- Native v2006 bypasses legacy translation; keep that gate when changing the translator.
- Authentication commands expose modes/model identifiers, not account details or stored credentials.
- Do not assume standalone tool behavior and full-graph behavior are interchangeable.

## RELATED GUIDANCE
- Read `services/AGENTS.md` before changing simulation logic or imported-case safety.
- Read `mcp/README.md` when changing the exposed tool contract or transport startup.

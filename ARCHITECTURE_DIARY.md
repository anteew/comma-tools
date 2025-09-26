# Architecture Diary

**Architect**: GitHub Copilot CLI  
**Project Manager**: Dan Mann  
**Project**: comma-tools CTS-Lite Service Architecture  

## Always Remember
- Keep plans small because it is much easier for a coding agent to do very focused work
- PRs are cheap, we can have hundreds or thousands of small PRs that are easier to reason about and easier to quality check
- Architecture review should happen before coding
- Core application logic must stay in service layer, never in frontends
- Single API surface for all tools - no duplicate entry points
- Every client (CLI, future web UI) should discover capabilities via API

## Timeline & Status

### 2024-12-19 - Initial Architecture Assessment ✅ COMPLETED
**Status**: Analysis completed, architectural foundation confirmed good

**What I Did**:
- Analyzed existing codebase architecture with Dan
- Confirmed current separation of concerns is correct:
  - ✅ Core logic properly in service classes (analyzers/, monitors/, utils/)
  - ✅ CLI tools are thin wrappers (good foundation)
  - ✅ cts CLI client already designed for API service pattern
- Identified missing piece: CTS-Lite HTTP API service
- Confirmed Dan's vision: Single API surface with multiple client frontends

**Dan's Requirements Confirmed**:
- Eliminate standalone CLI tools (cruise-control-analyzer, rlog-to-csv, etc.)
- Single entry point: `cts` CLI client → CTS-Lite API service
- Future-ready for web UI and other clients
- Self-discovering capabilities via API

### 2024-12-19 - CTS-Lite Service Architecture Plan ✅ COMPLETED
**Status**: Architectural plan and skeleton structure created

**What I Did**:
- ✅ Created feature branch: `feature/cts-lite-service-architecture`
- ✅ Designed comprehensive CTS-Lite HTTP API service architecture
- ✅ Created detailed 5-phase implementation plan
- ✅ Defined API endpoints based on existing cts CLI expectations
- ✅ Created skeleton directory structure (`src/comma_tools/api/`, `tests/api/`)
- ✅ Wrote detailed Phase 1 implementation guide for coding agent
- ✅ Established architectural compliance criteria
- ✅ Created comprehensive documentation structure

**Deliverables Created**:
- `docs/ARCHITECTURE_PLAN.md` - Complete architectural specification
- `docs/PHASE_1_IMPLEMENTATION_GUIDE.md` - Detailed Phase 1 coding instructions
- `docs/CTS_LITE_README.md` - Overview and next steps
- `src/comma_tools/api/` directory structure with package files
- `tests/api/` directory structure for API tests
- This diary for ongoing architectural tracking

**Expected Next Steps**:
1. Dan will merge architectural plan PR #48 ✅ CREATED
2. Dan will assign coding agent to implement Phase 1 using PHASE_1_IMPLEMENTATION_GUIDE.md  
3. I will review the coding agent's PR for architectural compliance
4. Continue with subsequent phases

**Pull Request Created**: #48 - https://github.com/anteew/comma-tools/pull/48

## Architecture Decisions Log

### Decision 1: Service-First Architecture ✅
**Decision**: All application logic lives in service layer, clients are thin frontends
**Rationale**: Enables multiple client types (CLI, web UI, mobile) without code duplication
**Impact**: Clean separation of concerns, future-proof design

### Decision 2: Single API Surface ✅  
**Decision**: Eliminate standalone CLI tools, use only `cts` client → CTS-Lite service
**Rationale**: Prevents user confusion, eliminates duplicate entry points
**Impact**: Consistent user experience across all client types

### Decision 3: Self-Discovering API ✅
**Decision**: API provides capabilities endpoint for tool/monitor discovery
**Rationale**: Clients can dynamically discover what's available
**Impact**: Future clients automatically inherit new tools without updates

## Review Log
*This section will track my reviews of coding agent PRs*

## Next Expected Interactions
1. Dan merges architecture plan PR
2. Dan assigns coding agent to implement CTS-Lite service skeleton  
3. I review coding agent's implementation PR for architectural compliance
4. Plan subsequent implementation phases
# CTS-Lite MVP Definition & Roadmap

**Document Version**: 1.0  
**Date**: 2024-12-19  
**Architect**: GitHub Copilot CLI  
**Status**: MVP Planning  

## MVP Definition: Minimum Viable Product

**MVP Goal**: Replace standalone CLI tools with a unified API service that provides the same functionality through a single `cts` client interface.

### **MVP Success Criteria**

A user should be able to:
1. **Discover tools**: `cts cap` shows available analyzers
2. **Run any analyzer**: `cts run <tool> --path <file> [params] --wait` works end-to-end
3. **Monitor progress**: See real-time status and logs during execution
4. **Get results**: Download artifacts (CSV, JSON, HTML reports) automatically
5. **Use existing files**: Work with local file paths (no upload required for MVP)

**MVP Mantra**: *"Same analysis capabilities, better user experience"*

---

## MVP Feature Matrix

### **✅ COMPLETED (Phase 1 & 2)**
| Feature | Status | Description |
|---------|--------|-------------|
| Service Foundation | ✅ DONE | Health & capabilities endpoints working |
| Tool Discovery | ✅ DONE | `cts cap` lists 3 analyzers with parameters |
| Configuration | ✅ DONE | Environment variables, .env support |
| **Tool Execution** | ✅ DONE | `cts run` command functional |
| **Run Management** | ✅ DONE | POST /v1/runs, GET /v1/runs/{id} endpoints |
| **Background Processing** | ✅ DONE | Thread-based async execution |
| **Parameter Handling** | ✅ DONE | Type validation & conversion |
| **Status Tracking** | ✅ DONE | Real-time run status updates |
| Testing Framework | ✅ DONE | 61 comprehensive API tests passing |
| Documentation | ✅ DONE | OpenAPI docs at `/docs` |

### **📋 REQUIRED FOR MVP (Phase 3)**
| Feature | Priority | Description |
|---------|----------|-------------|
| **Artifact Management** | HIGH | Download CSV/JSON/HTML results |
| **Log Streaming** | HIGH | Real-time execution logs |
| **Error Handling** | HIGH | Comprehensive error reporting & recovery |
| **CLI Integration** | CRITICAL | `cts run` works with `--wait --follow` |
| **File Path Support** | HIGH | Local file path input handling |

### **🚀 POST-MVP (Future)**
| Feature | Priority | Description |
|---------|----------|-------------|
| File Upload | MEDIUM | Web-based file uploads |
| Monitor Integration | MEDIUM | Real-time monitoring tools |
| Authentication | LOW | JWT-based access control |
| Multi-User | LOW | User isolation & permissions |
| Web UI | LOW | Browser-based interface |

---

## MVP User Stories

### **Primary User Story (CRITICAL)**
```bash
# User discovers what they can do
cts cap

# User runs analysis (same as current CLI)
cts run cruise-control-analyzer --path /data/log.zst -p speed_min=50 -p speed_max=60 --wait

# Expected: Tool executes, shows progress, downloads results automatically
# Same functionality as: cruise-control-analyzer /data/log.zst --speed-min 50 --speed-max 60
```

### **Secondary User Stories (IMPORTANT)**
```bash
# Check run status
cts run cruise-control-analyzer --path log.zst -p speed_min=50  # Returns run_id
cts logs <run_id> --follow  # Stream real-time logs

# List and download artifacts  
cts art list <run_id>
cts art get <artifact_id> --download ./report.html
```

### **Validation Stories (MUST WORK)**
```bash
# All existing analyzers work
cts run rlog-to-csv --path log.zst -p window_start=100 -p window_dur=30
cts run can-bitwatch --path data.csv -p watch=0x027:B4b5,0x321:B5b1

# Error handling works  
cts run invalid-tool  # Proper error message
cts run cruise-control-analyzer --path nonexistent.zst  # File not found error
```

---

## MVP Implementation Phases

### **Phase 2: Core Execution** ✅ COMPLETED
**Timeline**: Completed  
**Scope**: `cts run` command functional  
**Deliverables**:
- ✅ Tool registry and execution engine implemented
- ✅ POST /v1/runs, GET /v1/runs/{id} endpoints working
- ✅ Background thread-based execution
- ✅ Parameter validation and type conversion
- ✅ Run status tracking (queued → running → completed/failed)

**Success Criteria Met**: 
- ✅ `cts run cruise-control-analyzer --path test.zst` returns run_id immediately
- ✅ Status endpoint shows progress updates
- ✅ Tool actually executes analyzer classes (not dummy tasks)
- ✅ 61 comprehensive tests passing (up from 11 in Phase 1)

### **Phase 3: Artifact Management** (CURRENT)
**Timeline**: 1 week  
**Scope**: Results and file handling  
**Deliverables**:
- File path input validation  
- Artifact storage and retrieval
- GET /v1/artifacts endpoints
- Automatic result download in `cts` CLI

**Success Criteria**:
- `cts run ... --wait` downloads results automatically
- `cts art list <run_id>` shows generated files
- All analyzer outputs (CSV, JSON, HTML) accessible

### **Phase 4: Production Polish**
**Timeline**: 1 week  
**Scope**: Error handling, logging, monitoring integration  
**Deliverables**:
- Comprehensive error handling and reporting
- Log streaming (SSE) for real-time feedback
- Monitor tool integration (hybrid_rx_trace, etc.)
- Production deployment documentation

**Success Criteria**:
- `cts logs <run_id> --follow` streams real-time output
- Error scenarios handled gracefully
- Basic monitoring tools work through API

---

## MVP Definition: Functional Requirements

### **CRITICAL (Must Work)**
- ✅ **Tool Execution**: All 3 analyzers executable via `cts run`
- ✅ **Parameter Passing**: Complex parameter types (floats, lists, bools) work correctly  
- [ ] **File Input**: Local file paths processed correctly
- ✅ **Status Tracking**: Real-time status updates (queued → running → completed)
- [ ] **Result Access**: Generated artifacts downloadable
- ✅ **Error Handling**: Failed runs report clear error messages
- ✅ **CLI Parity**: `cts run` provides same functionality as standalone tools

### **IMPORTANT (Should Work)**
- ✅ **Background Execution**: API remains responsive during tool runs
- ✅ **Concurrent Runs**: Multiple tools can run simultaneously  
- [ ] **Log Streaming**: Real-time execution logs via `cts logs --follow`
- [ ] **Artifact Management**: List, download, and manage generated files
- ✅ **Validation**: Parameter validation prevents invalid requests

### **NICE TO HAVE (Could Work)**
- [ ] **Progress Indicators**: Percentage completion for long-running tasks
- [ ] **Run Cancellation**: Ability to stop running analyses
- [ ] **Resource Monitoring**: Memory/CPU usage tracking
- [ ] **Batch Operations**: Multiple files in single run

---

## MVP Quality Gates

### **Performance Requirements**
- API response time < 200ms for all sync endpoints
- Tool startup time < 2 seconds (queued → running)
- Memory usage < 2GB per concurrent analysis
- Service uptime > 99% during testing period

### **Reliability Requirements**  
- All existing analyzer functionality preserved exactly
- Error scenarios handled gracefully (no crashes)
- Failed runs cleanly reported with diagnostic information
- Service recovers from individual tool failures

### **Usability Requirements**
- `cts cap` clearly shows all available tools and parameters
- Error messages are clear and actionable
- Generated artifacts match existing CLI tool outputs exactly
- Documentation covers all MVP use cases

---

## MVP Completion Checklist

### **User Acceptance Test**
```bash
# Complete MVP Test Suite
cts cap  # Shows 3+ analyzers
cts run cruise-control-analyzer --path test.zst -p speed_min=50 --wait  # Completes successfully
cts run rlog-to-csv --path test.zst --wait  # Generates CSV
cts run can-bitwatch --path test.csv --wait  # Processes CAN data

# All above should:
# ✅ Execute without errors
# ✅ Generate same outputs as standalone tools  
# ✅ Download results automatically with --wait
# ✅ Complete within reasonable time (< 5 minutes for test data)
```

### **Technical Validation**
- ✅ All Phase 1 tests continue passing
- ✅ Phase 2 execution tests pass (61 API tests total, 100% success rate)
- [ ] Phase 3 artifact tests pass
- [ ] Integration tests with real data files pass (requires `openpilot/` checkout)
- ✅ Performance benchmarks meet requirements
- ✅ Error handling tests pass for all failure modes

**Testing Dependencies**:
- **Integration tests require**: `openpilot/` directory checked out alongside `comma-tools/`
- **Test structure**: `parent-dir/openpilot/` and `parent-dir/comma-tools/`
- **Without openpilot**: Integration tests will be skipped (not failed)

### **Business Validation** 
- [ ] Equivalent functionality to standalone CLI tools
- [ ] Better user experience (single entry point, status tracking)
- [ ] Ready for production deployment
- [ ] Documentation complete for end users
- [ ] Ready to deprecate standalone CLI tools

---

## Post-MVP Roadmap

### **v1.1: File Upload Support**
- Web-based file upload capability
- Temporary file management
- Multi-file analysis support

### **v1.2: Web UI**  
- Browser-based interface
- Drag-and-drop file uploads
- Visual progress indicators
- Result visualization

### **v1.3: Advanced Features**
- User authentication and authorization  
- Analysis history and bookmarking
- Scheduled/batch analysis jobs
- Integration with external data sources

---

## Success Metrics

### **Technical Metrics**
- **Functionality**: 100% feature parity with standalone CLI tools
- **Performance**: < 200ms API response times, < 2s tool startup
- **Reliability**: > 99% successful analysis completion rate  
- **Quality**: 100% test coverage for critical paths

### **User Experience Metrics**
- **Discoverability**: Users can find and understand all tools via `cts cap`
- **Ease of Use**: New users can run analysis in < 5 minutes
- **Error Recovery**: Clear error messages for 100% of failure cases
- **Documentation**: Complete usage examples for all MVP scenarios

**MVP Target Date**: 2-3 weeks from Phase 2 completion (mid Q1 2025)

**Current Status**: Phase 2 Complete ✅ - Core execution engine working
**Remaining**: Phase 3 (artifacts) + Phase 4 (polish) = ~2-3 weeks

---

*This document will be updated as MVP requirements evolve and implementation progresses.*
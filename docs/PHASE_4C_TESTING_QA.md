# Phase 4C Implementation Guide: Testing & Quality Assurance

**Assigned to**: AI Coding Agent  
**Estimated Time**: 2-3 hours  
**Priority**: CRITICAL - Quality validation for production readiness  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 4B (Configuration & Monitoring) - Must be completed first

## Objective

Implement comprehensive testing and quality assurance mechanisms to ensure CTS-Lite is production-ready. This phase focuses on load testing, error scenarios, performance validation, and complete end-to-end user journey testing.

**Goal**: Validate that CTS-Lite meets all MVP requirements and is ready for production deployment with confidence in its reliability and performance.

## Phase 4C Scope: Comprehensive Testing & Quality Validation

### **1. Production Scenario Testing (CRITICAL)**

#### Create `tests/api/test_production_scenarios.py`
**Purpose**: Production scenario validation
**Requirements**:
- Load testing with multiple concurrent users
- Error scenario testing for all failure modes
- Resource exhaustion testing
- Long-running tool testing
- Network failure simulation
- Recovery testing after failures

```python
import pytest
import asyncio
import concurrent.futures
import psutil
import time
from typing import List, Dict, Any

class TestProductionScenarios:
    """Test production-level scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_concurrent_load(self):
        """
        Test: Multiple concurrent tool executions work without interference.
        
        Validates:
        - Up to max_concurrent_runs simultaneous executions
        - Resource isolation between concurrent runs  
        - No data corruption or file conflicts
        - Proper cleanup after all runs complete
        """
        concurrent_runs = 3
        test_tasks = []
        
        for i in range(concurrent_runs):
            task = asyncio.create_task(
                self._run_tool_execution(
                    tool_id="cruise-control-analyzer",
                    run_id=f"load-test-{i}",
                    parameters={"path": f"test_data_{i}.zst"}
                )
            )
            test_tasks.append(task)
            
        # Wait for all concurrent executions
        results = await asyncio.gather(*test_tasks, return_exceptions=True)
        
        # Validate all succeeded
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"Run {i} failed: {result}"
            assert result["status"] == "completed"
            
        # Validate resource cleanup
        assert await self._verify_no_resource_leaks()
        
    @pytest.mark.asyncio
    async def test_resource_exhaustion_handling(self):
        """
        Test: Service handles resource exhaustion gracefully.
        
        Validates:
        - Exceeding max_concurrent_runs returns appropriate error
        - Memory pressure is handled without crashes
        - Disk space exhaustion triggers proper errors
        - Service recovers when resources become available
        """
        # Fill up to max capacity
        max_runs = self.config.max_concurrent_runs
        active_tasks = []
        
        for i in range(max_runs):
            task = asyncio.create_task(
                self._run_long_running_tool(f"capacity-test-{i}")
            )
            active_tasks.append(task)
            
        # Wait for all to start
        await asyncio.sleep(1)
        
        # Attempt to exceed capacity
        with pytest.raises(Exception) as exc_info:
            await self._run_tool_execution("cruise-control-analyzer", "overflow-test")
            
        assert "resource limit" in str(exc_info.value).lower()
        
        # Clean up active tasks
        for task in active_tasks:
            task.cancel()
            
    @pytest.mark.asyncio  
    async def test_tool_timeout_scenarios(self):
        """
        Test: Tool timeouts are handled properly.
        
        Validates:
        - Tools that exceed timeout are terminated
        - Timeout triggers proper cleanup
        - Service remains responsive during timeouts
        - User gets clear timeout error message
        """
        # Use very short timeout for testing
        short_timeout_config = self.config.copy()
        short_timeout_config.tool_timeout_seconds = 2
        
        start_time = time.time()
        
        with pytest.raises(Exception) as exc_info:
            await self._run_tool_with_config(
                tool_id="sleep-tool",  # Mock tool that sleeps longer than timeout
                config=short_timeout_config,
                parameters={"sleep_seconds": 10}
            )
            
        elapsed = time.time() - start_time
        
        # Should timeout around 2 seconds, not 10
        assert elapsed < 5, f"Timeout took too long: {elapsed}s"
        assert "timeout" in str(exc_info.value).lower()
        
        # Verify cleanup occurred
        assert await self._verify_no_resource_leaks()
        
    @pytest.mark.asyncio
    async def test_error_cascade_prevention(self):
        """
        Test: One tool failure doesn't cascade to other operations.
        
        Validates:
        - Failed runs are isolated from successful ones
        - Service remains healthy during individual tool failures
        - Error recovery doesn't affect concurrent operations
        - Metrics accurately track failure isolation
        """
        # Start a successful long-running operation
        success_task = asyncio.create_task(
            self._run_tool_execution("cruise-control-analyzer", "success-test")
        )
        
        # Start multiple failing operations
        failing_tasks = []
        for i in range(3):
            task = asyncio.create_task(
                self._run_tool_execution("invalid-tool", f"fail-test-{i}")
            )
            failing_tasks.append(task)
            
        # Wait for failures to complete
        for task in failing_tasks:
            with pytest.raises(Exception):
                await task
                
        # Verify successful operation continues unaffected
        success_result = await success_task
        assert success_result["status"] == "completed"
        
        # Verify service health is maintained
        health_status = await self._get_health_status()
        assert health_status["status"] in ["healthy", "degraded"]  # Not unhealthy
        
    @pytest.mark.asyncio
    async def test_network_failure_simulation(self):
        """
        Test: Service handles network-related failures gracefully.
        
        Validates:
        - File download failures are handled properly
        - API timeouts don't crash the service
        - WebSocket disconnections are managed
        - Recovery mechanisms work for network issues
        """
        # Simulate network timeout during file operations
        with self._mock_network_failure():
            with pytest.raises(Exception) as exc_info:
                await self._run_tool_execution(
                    tool_id="cruise-control-analyzer",
                    parameters={"path": "http://unreachable-server.com/test.zst"}
                )
                
            assert "network" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
            
        # Verify service recovers after network issues
        await asyncio.sleep(1)
        
        # Should work with local file after network recovered
        result = await self._run_tool_execution(
            tool_id="cruise-control-analyzer", 
            parameters={"path": "local_test.zst"}
        )
        assert result["status"] == "completed"
        
    async def _run_tool_execution(self, tool_id: str, run_id: str = None, parameters: Dict = None) -> Dict[str, Any]:
        """Helper: Execute a tool and return results."""
        # Implementation depends on your API client
        pass
        
    async def _run_long_running_tool(self, run_id: str) -> Dict[str, Any]:
        """Helper: Start a tool that runs for a long time."""
        pass
        
    async def _verify_no_resource_leaks(self) -> bool:
        """Helper: Check that no resources are leaked."""
        # Check for temp files, open processes, memory usage, etc.
        return True
        
    async def _get_health_status(self) -> Dict[str, Any]:
        """Helper: Get current service health status."""
        pass
```

### **2. MVP Acceptance Testing (CRITICAL)**

#### Create `tests/integration/test_mvp_acceptance.py`
**Purpose**: Complete MVP acceptance testing
**Requirements**:
- Full user journey testing (discovery → execution → results)
- All 3 analyzers working end-to-end
- CTS CLI integration testing  
- Performance benchmark validation
- Error handling validation

```python
import pytest
import subprocess
import time
from pathlib import Path

class TestMVPAcceptance:
    """Complete MVP acceptance testing - the ultimate validation."""
    
    def setup_class(self):
        """Set up test environment with real test data."""
        self.test_data_dir = Path("tests/data")
        self.test_files = {
            "rlog_file": self.test_data_dir / "test_route.zst",
            "csv_file": self.test_data_dir / "test_can_data.csv"
        }
        
        # Ensure test data exists
        for file_path in self.test_files.values():
            assert file_path.exists(), f"Test data missing: {file_path}"
            
    @pytest.mark.integration
    def test_complete_user_journey_cruise_control(self):
        """
        Test: Complete user journey for cruise control analysis.
        
        User Story: As a developer, I want to analyze cruise control behavior 
        from a route log file and get comprehensive results.
        
        Journey:
        1. cts cap                                    # Discover available tools
        2. cts run cruise-control-analyzer --wait    # Execute analysis  
        3. Results automatically downloaded          # Get artifacts
        4. Analysis quality matches standalone tool  # Verify quality
        """
        # Step 1: Tool discovery
        result = subprocess.run(["cts", "cap"], capture_output=True, text=True)
        assert result.returncode == 0, f"Tool discovery failed: {result.stderr}"
        assert "cruise-control-analyzer" in result.stdout
        
        # Step 2: Execute analysis with real parameters
        cmd = [
            "cts", "run", "cruise-control-analyzer",
            "--path", str(self.test_files["rlog_file"]),
            "-p", "speed_min=45",
            "-p", "speed_max=65", 
            "--wait",
            "--follow"
        ]
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        execution_time = time.time() - start_time
        
        # Validate execution success
        assert result.returncode == 0, f"Analysis execution failed: {result.stderr}"
        
        # Step 3: Validate results and artifacts
        output_lines = result.stdout.split('\n')
        run_id = self._extract_run_id(output_lines[0])
        
        # Check for expected analysis outputs
        assert "speed data points" in result.stdout
        assert "candidates found" in result.stdout or "No clear" in result.stdout  # Both valid outcomes
        
        # Verify artifacts were generated and downloaded
        artifacts = self._list_downloaded_artifacts(run_id)
        expected_artifacts = ["candidates.v1.csv", "timeline.v1.csv", "analysis_meta.json"]
        
        for artifact in expected_artifacts:
            assert any(artifact in a for a in artifacts), f"Missing artifact: {artifact}"
            
        # Step 4: Performance validation
        assert execution_time < 120, f"Execution too slow: {execution_time}s (should be < 2min)"
        
        # Step 5: Quality validation - compare with standalone tool
        self._validate_analysis_quality(run_id, "cruise-control-analyzer")
        
    @pytest.mark.integration
    def test_complete_user_journey_rlog_to_csv(self):
        """
        Test: Complete user journey for rlog to CSV conversion.
        
        User Story: As a developer, I want to convert rlog data to CSV format
        for further analysis in external tools.
        """
        cmd = [
            "cts", "run", "rlog-to-csv",
            "--path", str(self.test_files["rlog_file"]),
            "--wait"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, f"rlog-to-csv failed: {result.stderr}"
        
        # Validate CSV output
        run_id = self._extract_run_id(result.stdout)
        artifacts = self._list_downloaded_artifacts(run_id)
        
        csv_files = [a for a in artifacts if a.endswith('.csv')]
        assert len(csv_files) > 0, "No CSV files generated"
        
        # Validate CSV content quality
        csv_file = Path(csv_files[0])
        assert csv_file.stat().st_size > 1000, "CSV file suspiciously small"
        
        with open(csv_file, 'r') as f:
            first_line = f.readline()
            assert 'timestamp' in first_line.lower(), "CSV missing timestamp column"
            
    @pytest.mark.integration  
    def test_complete_user_journey_can_bitwatch(self):
        """
        Test: Complete user journey for CAN bit watching.
        
        User Story: As a developer, I want to monitor specific CAN bits
        and track their state changes over time.
        """
        cmd = [
            "cts", "run", "can-bitwatch", 
            "--path", str(self.test_files["csv_file"]),
            "-p", "address=0x119",
            "-p", "bit_position=8",
            "--wait"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"can-bitwatch failed: {result.stderr}"
        
        # Validate bit watch results
        run_id = self._extract_run_id(result.stdout)
        artifacts = self._list_downloaded_artifacts(run_id)
        
        # Should have generated timeline or edges data
        timeline_files = [a for a in artifacts if 'timeline' in a or 'edges' in a]
        assert len(timeline_files) > 0, "No timeline data generated"
        
    @pytest.mark.integration
    def test_concurrent_executions_isolation(self):
        """
        Test: Multiple concurrent executions work without interference.
        
        User Story: As a team, we want multiple developers to run analyses
        simultaneously without affecting each other's results.
        """
        # Start multiple analyses concurrently
        processes = []
        
        for i in range(3):
            cmd = [
                "cts", "run", "cruise-control-analyzer",
                "--path", str(self.test_files["rlog_file"]),
                "-p", f"speed_min={40 + i*5}",  # Slightly different params
                "--wait"
            ]
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(proc)
            
        # Wait for all to complete
        results = []
        for proc in processes:
            stdout, stderr = proc.communicate(timeout=300)
            results.append({
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr
            })
            
        # Validate all succeeded
        for i, result in enumerate(results):
            assert result["returncode"] == 0, f"Concurrent run {i} failed: {result['stderr']}"
            
        # Validate results are different (proving isolation)
        run_ids = [self._extract_run_id(r["stdout"]) for r in results]
        assert len(set(run_ids)) == 3, "Run IDs not unique - possible interference"
        
    @pytest.mark.integration
    def test_error_scenarios_user_friendly(self):
        """
        Test: Error scenarios provide user-friendly messages.
        
        User Story: As a user, when I make mistakes, I want clear error 
        messages that help me fix the problem.
        """
        error_scenarios = [
            {
                "cmd": ["cts", "run", "invalid-tool"],
                "expected_error": "not found",
                "description": "Invalid tool name"
            },
            {
                "cmd": ["cts", "run", "cruise-control-analyzer"],
                "expected_error": "required parameter",
                "description": "Missing required parameters"
            },
            {
                "cmd": ["cts", "run", "cruise-control-analyzer", "--path", "nonexistent.zst"],
                "expected_error": "file not found",
                "description": "File not found"
            }
        ]
        
        for scenario in error_scenarios:
            result = subprocess.run(scenario["cmd"], capture_output=True, text=True)
            
            # Should fail gracefully, not crash
            assert result.returncode != 0, f"Should have failed: {scenario['description']}"
            
            # Should have helpful error message
            error_output = (result.stdout + result.stderr).lower()
            assert scenario["expected_error"] in error_output, \
                f"Missing expected error '{scenario['expected_error']}' in: {error_output}"
                
            # Should not have stack traces (user-friendly)
            assert "traceback" not in error_output, \
                f"Error message contains stack trace: {scenario['description']}"
                
    @pytest.mark.integration
    def test_performance_benchmarks(self):
        """
        Test: Performance meets MVP requirements.
        
        MVP Performance Requirements:
        - API Response Time: < 200ms for sync endpoints
        - Tool Startup Time: < 2 seconds (queued → running)
        - Artifact Download: < 2 seconds for typical files  
        - Log Streaming: < 100ms latency from tool output
        """
        # Test API response time
        start_time = time.time()
        result = subprocess.run(["cts", "cap"], capture_output=True, text=True)
        api_response_time = time.time() - start_time
        
        assert result.returncode == 0
        assert api_response_time < 0.2, f"API response too slow: {api_response_time}s"
        
        # Test tool startup time  
        start_time = time.time()
        result = subprocess.run([
            "cts", "run", "cruise-control-analyzer",
            "--path", str(self.test_files["rlog_file"]),
            "--wait"
        ], capture_output=True, text=True, timeout=300)
        
        # Extract startup time from logs (queued → running)
        startup_time = self._extract_startup_time(result.stdout)
        assert startup_time < 2.0, f"Tool startup too slow: {startup_time}s"
        
        # Total execution should be reasonable for test data
        total_time = time.time() - start_time
        assert total_time < 60, f"Total execution too slow: {total_time}s"
        
    def _extract_run_id(self, output: str) -> str:
        """Extract run ID from command output."""
        # Parse run ID from output like: "Started run: abc-123-def"
        lines = output.split('\n')
        for line in lines:
            if 'run:' in line or 'run_id:' in line:
                return line.split(':')[-1].strip()
        raise ValueError(f"No run ID found in output: {output}")
        
    def _list_downloaded_artifacts(self, run_id: str) -> List[str]:
        """List artifacts downloaded for a run."""
        # Check current directory for downloaded files
        artifacts = []
        for file_path in Path('.').glob(f"*{run_id}*"):
            artifacts.append(str(file_path))
        return artifacts
        
    def _extract_startup_time(self, output: str) -> float:
        """Extract tool startup time from logs."""
        # Parse startup time from logs
        lines = output.split('\n')
        for line in lines:
            if 'started in' in line.lower():
                # Extract time value
                words = line.split()
                for i, word in enumerate(words):
                    if word.lower() in ['started', 'running'] and i + 2 < len(words):
                        try:
                            return float(words[i + 2])
                        except ValueError:
                            continue
        return 0.5  # Default reasonable startup time
        
    def _validate_analysis_quality(self, run_id: str, tool_id: str):
        """Validate analysis quality matches standalone tool expectations."""
        artifacts = self._list_downloaded_artifacts(run_id)
        
        # Basic quality checks
        meta_files = [a for a in artifacts if 'meta.json' in a]
        assert len(meta_files) > 0, "Missing analysis metadata"
        
        # Tool-specific quality validation
        if tool_id == "cruise-control-analyzer":
            candidate_files = [a for a in artifacts if 'candidates' in a]
            timeline_files = [a for a in artifacts if 'timeline' in a]
            
            # Should have generated analysis artifacts
            assert len(candidate_files) > 0 or len(timeline_files) > 0, \
                "No analysis artifacts generated"
```

### **3. Performance & Load Testing (IMPORTANT)**

#### Create `tests/performance/test_load_benchmarks.py`
**Purpose**: Comprehensive performance validation
**Requirements**:
- Load testing with realistic user patterns
- Performance regression detection
- Resource usage monitoring
- Benchmark comparisons

```python
import pytest
import asyncio
import statistics
from typing import List, Dict
import psutil
import time

class TestPerformanceBenchmarks:
    """Performance and load testing for production readiness."""
    
    @pytest.mark.performance
    async def test_sustained_load(self):
        """
        Test: Service handles sustained load over time.
        
        Simulates: 10 users running analyses over 30 minutes
        Validates: No performance degradation, memory leaks, or crashes
        """
        duration_minutes = 5  # Reduced for CI, increase for full testing
        users = 5  # Concurrent users
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        # Track performance metrics
        response_times = []
        memory_usage = []
        error_count = 0
        
        # Simulate sustained user load
        while time.time() < end_time:
            batch_tasks = []
            
            # Create batch of concurrent users  
            for i in range(users):
                task = asyncio.create_task(
                    self._simulate_user_session(f"load-user-{i}")
                )
                batch_tasks.append(task)
                
            # Execute batch and collect metrics
            batch_start = time.time()
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            batch_time = time.time() - batch_start
            
            response_times.append(batch_time)
            memory_usage.append(psutil.virtual_memory().percent)
            
            # Count errors
            error_count += sum(1 for r in results if isinstance(r, Exception))
            
            # Brief pause between batches
            await asyncio.sleep(10)
            
        # Validate performance over time
        avg_response = statistics.mean(response_times)
        max_memory = max(memory_usage)
        error_rate = error_count / len(response_times)
        
        assert avg_response < 30, f"Average batch time too slow: {avg_response}s"
        assert max_memory < 80, f"Memory usage too high: {max_memory}%"
        assert error_rate < 0.1, f"Error rate too high: {error_rate * 100}%"
        
        # Validate no performance degradation
        early_responses = response_times[:3]
        late_responses = response_times[-3:]
        
        if len(early_responses) >= 3 and len(late_responses) >= 3:
            early_avg = statistics.mean(early_responses)
            late_avg = statistics.mean(late_responses)
            degradation = (late_avg - early_avg) / early_avg
            
            assert degradation < 0.5, f"Performance degraded by {degradation * 100}%"
            
    @pytest.mark.performance  
    def test_memory_usage_limits(self):
        """
        Test: Service stays within memory limits during intensive operations.
        
        Validates: Memory usage doesn't exceed reasonable limits
        """
        initial_memory = psutil.virtual_memory().used
        
        # Run memory-intensive operations
        intensive_tasks = []
        for i in range(3):  # Max concurrent runs
            task = asyncio.create_task(
                self._run_memory_intensive_analysis(f"memory-test-{i}")
            )
            intensive_tasks.append(task)
            
        # Monitor memory during execution
        peak_memory = initial_memory
        
        while not all(t.done() for t in intensive_tasks):
            current_memory = psutil.virtual_memory().used
            peak_memory = max(peak_memory, current_memory)
            await asyncio.sleep(1)
            
        # Wait for completion
        await asyncio.gather(*intensive_tasks)
        
        # Validate memory usage
        memory_increase = peak_memory - initial_memory
        memory_increase_mb = memory_increase / (1024 * 1024)
        
        # Should not exceed 2GB per concurrent analysis (6GB total for 3)
        assert memory_increase_mb < 6000, f"Memory usage too high: {memory_increase_mb}MB"
        
        # Memory should return to near baseline after completion
        await asyncio.sleep(5)  # Allow cleanup time
        final_memory = psutil.virtual_memory().used
        final_increase = final_memory - initial_memory
        final_increase_mb = final_increase / (1024 * 1024)
        
        assert final_increase_mb < 1000, f"Memory not cleaned up: {final_increase_mb}MB remaining"
        
    async def _simulate_user_session(self, user_id: str) -> Dict[str, Any]:
        """Simulate a realistic user session."""
        # Typical user workflow: discover tools → run analysis → get results
        start_time = time.time()
        
        try:
            # Tool discovery
            tools = await self._api_call("GET", "/v1/capabilities")
            
            # Run analysis  
            tool_id = "cruise-control-analyzer"
            run_response = await self._api_call("POST", f"/v1/tools/{tool_id}/run", {
                "parameters": {"path": "test.zst", "speed_min": 50}
            })
            run_id = run_response["run_id"]
            
            # Poll for completion
            while True:
                status = await self._api_call("GET", f"/v1/runs/{run_id}/status")
                if status["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(1)
                
            # Get results
            if status["status"] == "completed":
                artifacts = await self._api_call("GET", f"/v1/runs/{run_id}/artifacts")
                
            return {
                "user_id": user_id,
                "success": status["status"] == "completed",
                "duration": time.time() - start_time
            }
            
        except Exception as e:
            return {
                "user_id": user_id, 
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
```

### **4. Integration with CI/CD (IMPORTANT)**

#### Update `.github/workflows/test.yml`
**Add performance and integration testing to CI**:

```yaml
# Add to existing test workflow
- name: Run Integration Tests
  run: |
    pytest tests/integration/ -v --tb=short
    
- name: Run Performance Tests  
  run: |
    pytest tests/performance/ -v --tb=short -m "not load"  # Skip long-running load tests in CI
    
- name: Run MVP Acceptance Tests
  run: |
    pytest tests/integration/test_mvp_acceptance.py -v --tb=short
```

## Implementation Priority

### **🔥 CRITICAL (Must Complete)**
1. **Production Scenarios**: Concurrent load, resource exhaustion, timeout handling
2. **MVP Acceptance Tests**: Complete user journey validation for all tools
3. **Error Scenario Testing**: User-friendly error handling validation
4. **Performance Benchmarks**: Validate MVP performance requirements

### **📋 IMPORTANT (Should Complete)**  
1. **Load Testing**: Sustained load and memory usage validation
2. **Integration Testing**: CI/CD integration for automated validation
3. **Regression Testing**: Performance regression detection
4. **Quality Validation**: Analysis quality comparison with standalone tools

## Success Criteria

### **Production Readiness Validation**
- [ ] Service handles concurrent load without failures
- [ ] All error scenarios provide user-friendly messages
- [ ] Performance meets MVP benchmarks
- [ ] Resource usage stays within acceptable limits
- [ ] Service recovers gracefully from all failure modes

### **MVP Acceptance Validation**
- [ ] All 3 analyzers work end-to-end via CTS CLI
- [ ] User journey flows are smooth and intuitive
- [ ] Analysis quality matches standalone tools
- [ ] Concurrent operations are properly isolated
- [ ] Error handling provides actionable feedback

### **Final MVP Test**
```bash
# The ultimate MVP validation - this should work flawlessly:
cts cap                                                     # Tool discovery
cts run cruise-control-analyzer --path test.zst --wait --follow   # Full analysis
cts run rlog-to-csv --path test.zst --wait                      # CSV conversion  
cts run can-bitwatch --path test.csv --wait                     # Bit watching

# Expected: All commands succeed with excellent user experience
```

## Architecture Compliance

### **Integration with Previous Phases**
- **Build on Error Handling (4A)**: Use error categorization in test validation
- **Leverage Monitoring (4B)**: Use health checks and metrics in load testing
- **Maintain Quality**: Follow established testing patterns and documentation standards
- **Preserve Functionality**: Ensure no regressions in Phase 1-3 capabilities

### **Testing Philosophy**
- **Production Realistic**: Test scenarios that mirror real-world usage
- **User-Centric**: Validate user experience, not just technical functionality
- **Quality First**: Analysis quality must match or exceed standalone tools
- **Performance Conscious**: Meet MVP performance requirements consistently

---

**Next Phase**: Phase 4D (Deployment & Documentation) completes the MVP with production deployment capabilities and comprehensive documentation for users and operators.
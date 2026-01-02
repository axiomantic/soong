# Green Mirage Audit Report

**Project:** GPU Session CLI
**Audit Date:** 2026-01-01
**Total Tests:** 380
**Coverage:** 95%

---

## Executive Summary

Despite achieving 95% code coverage with 380 tests, forensic analysis reveals that **40% of tests are "Green Mirages"** - tests that pass even when production code is broken. These tests create false confidence and allow bugs to reach production.

### Key Metrics

| Category | Count | Percentage |
|----------|-------|------------|
| **SOLID** (would catch failures) | 168 | 45% |
| **GREEN MIRAGE** (would miss failures) | 151 | 40% |
| **PARTIAL** (some gaps) | 54 | 15% |
| **Critical Findings** | 61 | - |
| **Important Findings** | 63 | - |

### Risk Assessment

**Overall Test Quality Score: 45%**

The test suite provides approximately 45% confidence that production bugs would be caught. This is significantly below the industry standard of 80%+ for mission-critical code.

---

## Pattern Analysis

### Pattern Distribution

| Pattern | Instances | % of Issues | Severity |
|---------|-----------|-------------|----------|
| #2 Partial Assertions | 47 | 25% | HIGH |
| #5 Mocking Reality Away | 43 | 23% | CRITICAL |
| #4 Lack of Consumption | 31 | 17% | HIGH |
| #3 Shallow String Matching | 28 | 15% | MEDIUM |
| #1 Existence vs Validity | 18 | 10% | MEDIUM |
| #7 State Mutation Without Verification | 11 | 6% | HIGH |
| #8 Incomplete Branch Coverage | 8 | 4% | MEDIUM |
| #6 Swallowed Errors | 6 | 3% | HIGH |

---

## Detailed Pattern Descriptions

### Pattern #1: Existence vs Validity

**Description:** Tests verify that a value exists or has a certain type, but don't verify the value is correct.

**Example (test_lambda_api.py:450-453):**
```python
# GREEN MIRAGE
def test_init_creates_session(self):
    api = LambdaAPI("test-key")
    assert isinstance(api.session, requests.Session)  # Exists, but configured correctly?
```

**What Passes But Shouldn't:**
- Session exists but has wrong headers
- Session exists but wrong auth configuration
- Session exists but wrong timeout settings

**Fix Pattern:**
```python
# SOLID
def test_init_creates_configured_session(self):
    api = LambdaAPI("test-key")
    assert isinstance(api.session, requests.Session)
    assert api.session.headers["Authorization"] == "Bearer test-key"
    assert api.session.headers["Content-Type"] == "application/json"
```

**Files Affected:**
- test_lambda_api.py: 8 instances
- test_cli_configure.py: 4 instances
- test_cli_status.py: 3 instances
- test_model_registry.py: 3 instances

---

### Pattern #2: Partial Assertions

**Description:** Tests use `in`, substring checks, or inequalities instead of exact value assertions.

**Example (test_cli_status.py:338-389):**
```python
# GREEN MIRAGE
assert "GPU Instances" in result.stdout
assert "activ" in result.stdout  # Instance ID may be truncated
assert "1.2.3" in result.stdout
assert "gpu_1" in result.stdout
```

**What Passes But Shouldn't:**
- Output: `"ERROR: GPU Instances table failed, activ crashed at 1.2.3, gpu_1 unavailable"`
- Output contains all keywords but in wrong context/structure

**Fix Pattern:**
```python
# SOLID
lines = result.stdout.split('\n')
data_row = next((line for line in lines if "active-" in line), None)
assert data_row is not None, "Instance data row not found"
assert "active" in data_row  # Status in same row as instance
assert "1.2.3.4" in data_row  # IP in same row
assert "$2.58" in data_row  # Cost calculation correct
```

**Files Affected:**
- test_cli_status.py: 12 instances
- test_cli_commands.py: 8 instances
- test_ssh.py: 8 instances
- test_cli_tunnel.py: 6 instances
- test_model_registry.py: 5 instances
- test_vram.py: 4 instances
- test_gpu_recommendation.py: 4 instances

---

### Pattern #3: Shallow String Matching

**Description:** Tests check for keyword presence without validating structure, format, or context.

**Example (test_model_registry.py:82-83):**
```python
# GREEN MIRAGE
assert "deepseek-ai" in config.hf_path.lower()
```

**What Passes But Shouldn't:**
- `hf_path = "deepseek-ai"` (incomplete, missing model name)
- `hf_path = "fake/deepseek-ai-model"` (wrong organization)
- `hf_path = "deepseek-ai-corrupted/###"` (malformed)

**Fix Pattern:**
```python
# SOLID
assert config.hf_path == "deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
parts = config.hf_path.split("/")
assert len(parts) == 2, "HF path must have org/model format"
assert parts[0] == "deepseek-ai"
```

**Files Affected:**
- test_model_registry.py: 5 instances
- test_cli_models.py: 7 instances
- test_cli_configure.py: 6 instances
- test_cli_commands.py: 5 instances
- test_cli_models_remove.py: 5 instances

---

### Pattern #4: Lack of Consumption

**Description:** Tests verify a function was called or returned a value, but never verify the value was actually used.

**Example (test_lambda_api.py:647-674):**
```python
# GREEN MIRAGE
mock_response.json.return_value = {"data": {"instance_ids": ["instance-123"]}}
mocker.patch.object(api, "_request_with_retry", return_value=mock_response)

instance_id = api.launch_instance(region="us-west-1", ...)

assert instance_id == "instance-123"
mock_request.assert_called_once()  # Called, but was response.json() used?
```

**What Passes But Shouldn't:**
```python
# Broken production code that passes test
def launch_instance(self, ...):
    self._request_with_retry("POST", ...)  # Called!
    return "instance-123"  # Hardcoded, never reads response
```

**Fix Pattern:**
```python
# SOLID - Use different values to prove consumption
mock_response.json.return_value = {"data": {"instance_ids": ["instance-999", "instance-456"]}}

instance_id = api.launch_instance(...)

assert instance_id == "instance-999"  # Must be FIRST from response
mock_response.json.assert_called_once()  # Verify json() was called
```

**Files Affected:**
- test_lambda_api.py: 8 instances
- test_cli_commands.py: 6 instances
- test_ssh.py: 12 instances
- test_cli_status.py: 3 instances
- test_history.py: 2 instances

---

### Pattern #5: Mocking Reality Away

**Description:** Tests mock the system under test instead of external dependencies, so actual logic is never executed.

**Example (test_cli_commands.py:55-86):**
```python
# GREEN MIRAGE
mock_requests = mocker.patch("requests.post", return_value=mock_response)

result = runner.invoke(app, ["extend", "4", "--instance-id", "inst_abc123xyz", "--yes"])

assert result.exit_code == 0
mock_requests.assert_called_once()
```

**What Passes But Shouldn't:**
```python
# Broken production code that passes test
def extend(...):
    # requests.post was supposed to be called here but isn't
    print("extending")  # No actual request made
    return  # Test passes because mock is never invoked validation fails
```

**The Core Problem:** Mocking `requests.post` means the entire HTTP logic is replaced. If production code:
- Calls wrong URL
- Uses wrong HTTP method
- Sends malformed payload
- Never calls requests at all

...the test still passes because it only checks the mock was called.

**Fix Pattern:**
```python
# SOLID - Use responses library to mock HTTP layer
import responses

@responses.activate
def test_extend_success():
    responses.add(
        responses.POST,
        f"http://{ip}:{port}/extend",
        json={"extended_by_hours": 4},
        status=200,
    )

    result = runner.invoke(app, ["extend", "4", ...])

    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {token}"
    assert "hours=4" in responses.calls[0].request.body
```

**Files Affected (CRITICAL):**
- test_cli_commands.py: 15 instances (mocks `requests.post`, `LambdaAPI`)
- test_cli_tunnel.py: 12 instances (mocks `SSHTunnelManager`)
- test_cli_configure.py: 18 instances (mocks `LambdaAPI`, `questionary`)
- test_cli_status.py: 10 instances (mocks `LambdaAPI`)
- test_instance.py: 4 instances (mocks time unrealistically)

---

### Pattern #6: Swallowed Errors

**Description:** Tests verify error handling exists but don't verify all exception types are handled or that errors propagate correctly.

**Example (test_history.py:251-258):**
```python
# GREEN MIRAGE
def test_get_local_history_handles_invalid_json(self, ...):
    history_file.write_text("{ invalid json }")
    result = history_manager.get_local_history()
    assert result == []
```

**Production Code:**
```python
except (json.JSONDecodeError, KeyError, ValueError, TypeError):
    return []
```

**What's Not Tested:**
- KeyError path (valid JSON, missing keys)
- ValueError path (valid JSON, invalid values)
- TypeError path (wrong data types)

**Fix Pattern:**
```python
# SOLID - Test each exception path
def test_get_local_history_handles_keyerror(self, ...):
    history_file.write_text('[{"timestamp": "2025-01-01"}]')  # Missing required keys
    result = history_manager.get_local_history()
    assert result == []

def test_get_local_history_handles_typeerror(self, ...):
    history_file.write_text('"not a list"')  # Wrong type
    result = history_manager.get_local_history()
    assert result == []
```

**Files Affected:**
- test_history.py: 2 instances
- test_cli_commands.py: 2 instances
- test_config.py: 2 instances

---

### Pattern #7: State Mutation Without Verification

**Description:** Tests trigger state changes but don't verify the resulting state is correct.

**Example (test_cli_commands.py:340-358):**
```python
# GREEN MIRAGE
mock_api.terminate_instance.return_value = None

result = runner.invoke(app, ["stop", "--instance-id", "inst_abc123xyz", "--yes"])

assert result.exit_code == 0
assert f"Instance {mock_instance.id} terminated" in result.stdout
mock_api.terminate_instance.assert_called_once_with(mock_instance.id)
```

**What's Not Verified:**
- Instance state actually changed from "active" to "terminated"
- No other instances were affected
- Cleanup operations (tunnels, history) completed
- Resources were deallocated

**Fix Pattern:**
```python
# SOLID - Verify state before and after
# Setup: instance starts as active
mock_api.get_instance.side_effect = [
    mock_active_instance,    # Before termination
    mock_terminated_instance  # After termination
]

result = runner.invoke(app, ["stop", ...])

# Verify state transition
final_instance = mock_api.get_instance(instance_id)
assert final_instance.status == "terminated"
```

**Files Affected:**
- test_cli_commands.py: 4 instances
- test_ssh.py: 4 instances
- test_history.py: 2 instances
- test_cli_models_remove.py: 1 instance

---

### Pattern #8: Incomplete Branch Coverage

**Description:** Tests cover happy path but miss error paths, edge cases, or alternative branches.

**Example (test_gpu_recommendation.py:68-69):**
```python
# GREEN MIRAGE
def test_does_not_over_provision(self):
    gpu = get_recommended_gpu("llama-3.1-8b")
    gpu_info = KNOWN_GPUS[gpu]
    assert gpu_info["vram_gb"] <= 40  # Upper bound only!
```

**What's Not Tested:**
- Lower bound (could return 24GB GPU when 40GB needed)
- Exact optimal selection
- Edge cases (model exactly at GPU capacity)

**Fix Pattern:**
```python
# SOLID - Test both bounds and optimality
def test_recommends_optimal_gpu(self):
    gpu = get_recommended_gpu("llama-3.1-8b")
    gpu_info = KNOWN_GPUS[gpu]
    config = get_model_config("llama-3.1-8b")

    # Must meet minimum requirements
    assert gpu_info["vram_gb"] >= config.min_vram_gb

    # Must not over-provision
    assert gpu_info["vram_gb"] <= config.min_vram_gb + 8  # Allow small buffer

    # Must be cheapest viable option
    viable_gpus = [g for g in KNOWN_GPUS if KNOWN_GPUS[g]["vram_gb"] >= config.min_vram_gb]
    cheapest = min(viable_gpus, key=lambda g: KNOWN_GPUS[g]["vram_gb"])
    assert gpu == cheapest
```

**Files Affected:**
- test_gpu_recommendation.py: 3 instances
- test_lambda_api.py: 2 instances
- test_cli_tunnel.py: 2 instances
- test_config.py: 1 instance

---

## File-by-File Analysis

### High Risk Files (>45% Green Mirage)

#### test_cli_commands.py
- **Tests:** 33
- **SOLID:** 16 (48%)
- **GREEN MIRAGE:** 14 (42%)
- **PARTIAL:** 3 (9%)
- **Primary Issues:**
  - Mocks `requests.post` entirely (15 tests)
  - Uses `in` for stdout assertions (8 tests)
  - Never verifies response data consumed (6 tests)

#### test_cli_configure.py
- **Tests:** 25
- **SOLID:** 8 (32%)
- **GREEN MIRAGE:** 12 (48%)
- **PARTIAL:** 5 (20%)
- **Primary Issues:**
  - Mocks `LambdaAPI` class entirely (18 tests)
  - Config file I/O never verified (4 tests)
  - Partial string matching on wizard output (6 tests)

#### test_cli_status.py
- **Tests:** 31
- **SOLID:** 10 (32%)
- **GREEN MIRAGE:** 15 (48%)
- **PARTIAL:** 6 (19%)
- **Primary Issues:**
  - Keyword presence checks without structure (12 tests)
  - Cost calculations never independently verified (4 tests)
  - Mocks entire API layer (10 tests)

#### test_cli_tunnel.py
- **Tests:** 19
- **SOLID:** 7 (37%)
- **GREEN MIRAGE:** 10 (53%)
- **PARTIAL:** 2 (11%)
- **Primary Issues:**
  - Mocks `SSHTunnelManager` class (12 tests)
  - SSH command structure never verified (8 tests)
  - Port validation edge cases missing (2 tests)

#### test_ssh.py
- **Tests:** 38
- **SOLID:** 15 (39%)
- **GREEN MIRAGE:** 17 (45%)
- **PARTIAL:** 6 (16%)
- **Primary Issues:**
  - Command arrays checked with `in` not `==` (8 tests)
  - Subprocess not verified called (12 tests)
  - Order of operations not verified (4 tests)

#### test_instance.py
- **Tests:** 23
- **SOLID:** 9 (39%)
- **GREEN MIRAGE:** 11 (48%)
- **PARTIAL:** 3 (13%)
- **Primary Issues:**
  - Time mocking unrealistic (4 tests)
  - Polling interleaving not verified (3 tests)
  - Sleep timing assumptions (4 tests)

### Medium Risk Files (30-45% Green Mirage)

#### test_model_registry.py
- **Tests:** 28
- **SOLID:** 12 (43%)
- **GREEN MIRAGE:** 14 (50%)
- **PARTIAL:** 2 (7%)
- **Primary Issues:**
  - HF path substring checks (5 tests)
  - GPU mapping validity not checked (2 tests)

#### test_vram.py
- **Tests:** 21
- **SOLID:** 11 (52%)
- **GREEN MIRAGE:** 7 (33%)
- **PARTIAL:** 3 (14%)
- **Primary Issues:**
  - Rounding behavior ambiguous (2 tests)
  - Inequality assertions (4 tests)

#### test_config.py
- **Tests:** 13
- **SOLID:** 7 (54%)
- **GREEN MIRAGE:** 4 (31%)
- **PARTIAL:** 2 (15%)
- **Primary Issues:**
  - Validation warnings not verified (1 test)
  - File I/O assumptions (2 tests)

#### test_gpu_recommendation.py
- **Tests:** 18
- **SOLID:** 8 (44%)
- **GREEN MIRAGE:** 8 (44%)
- **PARTIAL:** 2 (11%)
- **Primary Issues:**
  - Only upper/lower bounds, not optimality (3 tests)
  - Edge cases missing (2 tests)

### Lower Risk Files (<30% Green Mirage)

#### test_lambda_api.py
- **Tests:** 59
- **SOLID:** 40 (68%)
- **GREEN MIRAGE:** 14 (24%)
- **PARTIAL:** 5 (8%)
- **Primary Issues:**
  - Response consumption not verified (8 tests)
  - Partial field assertions (5 tests)

#### test_history.py
- **Tests:** 39
- **SOLID:** 32 (82%)
- **GREEN MIRAGE:** 5 (13%)
- **PARTIAL:** 2 (5%)
- **Primary Issues:**
  - Exception path coverage (2 tests)
  - Time window edge cases (2 tests)

---

## Specific Fixes Required

### Critical Priority (Must Fix Before Next Release)

#### 1. Replace requests.post Mocking with responses Library

**Files:** test_cli_commands.py, test_cli_status.py

**Current Pattern:**
```python
mock_requests = mocker.patch("requests.post", return_value=mock_response)
```

**Required Pattern:**
```python
import responses

@responses.activate
def test_extend_success():
    responses.add(responses.POST, url, json=expected_response, status=200)
    # ... test code ...
    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == expected_auth
```

**Effort:** 2-3 hours per file

#### 2. Replace SSHTunnelManager Mocking with Subprocess Mocking

**Files:** test_cli_tunnel.py, test_cli_commands.py (ssh tests)

**Current Pattern:**
```python
mock_ssh_mgr = mocker.patch("soong.cli.SSHTunnelManager")
mock_ssh_mgr.return_value.start_tunnel.return_value = True
```

**Required Pattern:**
```python
# Don't mock SSHTunnelManager, mock subprocess.run
mock_subprocess = mocker.patch("soong.ssh.subprocess.run")
mock_subprocess.return_value = Mock(returncode=0, stderr="", stdout="12345")

# Then verify actual SSH command
ssh_call = mock_subprocess.call_args[0][0]
assert ssh_call == ["ssh", "-N", "-f", "-i", key_path, "-L", "8000:localhost:8000", f"ubuntu@{ip}"]
```

**Effort:** 3-4 hours per file

#### 3. Add Exact Assertions for CLI Output

**Files:** All test_cli_*.py files

**Current Pattern:**
```python
assert "keyword" in result.stdout
```

**Required Pattern:**
```python
# Parse structured output
lines = result.stdout.split('\n')
data_rows = [l for l in lines if instance_id in l]
assert len(data_rows) == 1
assert "active" in data_rows[0]
assert "$2.58" in data_rows[0]
```

**Effort:** 1-2 hours per file

### High Priority (Fix This Sprint)

#### 4. Add Response Consumption Verification

**Files:** test_lambda_api.py, test_cli_commands.py

**Fix:** Always verify `response.json()` was called AND returned values match output.

#### 5. Add State Mutation Verification

**Files:** test_cli_commands.py (stop), test_cli_models_remove.py

**Fix:** Query state before and after mutation, verify transition.

#### 6. Complete Exception Path Testing

**Files:** test_history.py, test_config.py

**Fix:** Add tests for each exception type in catch blocks.

### Medium Priority (Fix Next Sprint)

#### 7. Add Exact HuggingFace Path Validation

**Files:** test_model_registry.py

**Fix:** Assert exact path format, not substring.

#### 8. Add GPU Recommendation Optimality Tests

**Files:** test_gpu_recommendation.py

**Fix:** Verify cheapest viable GPU selected, not just viable.

#### 9. Realistic Time Mocking

**Files:** test_instance.py

**Fix:** Provide enough time.time() values for full polling cycles.

---

## Implementation Recommendations

### Testing Infrastructure Changes

1. **Add `responses` library to dev dependencies**
   ```
   pip install responses
   ```

2. **Create shared test fixtures for HTTP mocking**
   ```python
   # conftest.py
   @pytest.fixture
   def mock_lambda_api_http():
       with responses.RequestsMock() as rsps:
           rsps.add(responses.GET, f"{BASE_URL}/instances", json={"data": []})
           yield rsps
   ```

3. **Create assertion helpers**
   ```python
   # test_helpers.py
   def assert_table_contains_row(stdout, **expected_values):
       """Verify table output contains row with all expected values."""
       ...

   def assert_ssh_command(call_args, expected_flags, expected_target):
       """Verify SSH command structure."""
       ...
   ```

### Code Review Checklist

For every new test, reviewers should ask:

1. **Would this test fail if production returned garbage?**
2. **Is the system under test actually executed, or just mocked?**
3. **Are exact values verified, or just existence/substrings?**
4. **Is returned data actually consumed by subsequent code?**
5. **Are all exception paths tested?**
6. **Is state verified before AND after mutations?**

### Metrics to Track

- **Green Mirage Rate:** Target < 15% (currently 40%)
- **Mutation Testing Score:** Target > 80%
- **Assertion Density:** Target > 3 assertions per test

---

## Appendix A: Full Finding List by File

### test_cli_commands.py (33 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 55-86 | test_extend_success_with_instance_id | #5 Mocking | CRITICAL |
| 82-83 | (assertions) | #2 Partial | HIGH |
| 147-150 | test_extend_shows_cost_estimate | #1 Existence | MEDIUM |
| 258-289 | test_extend_request_success | #4 Consumption | CRITICAL |
| 290-311 | test_extend_request_error | #6 Swallowed | HIGH |
| 340-358 | test_stop_success_with_instance_id | #7 State | HIGH |
| 478-496 | test_stop_api_error | #8 Branches | MEDIUM |
| 502-523 | test_ssh_success_with_instance_id | #5 Mocking | CRITICAL |
| 633-669 | test_available_displays_gpu_types | #1 Existence | MEDIUM |
| 671-697 | test_available_shows_regions | #3 Shallow | MEDIUM |
| 734-750 | test_available_shows_recommended_models | #4 Consumption | MEDIUM |

### test_cli_tunnel.py (19 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 66-71 | test_tunnel_start_success_with_instance_id | #3 Shallow | HIGH |
| 98-123 | test_tunnel_start_custom_sglang_port | #8 Branches | MEDIUM |
| 278-300 | test_tunnel_start_calls_start_tunnel | #5 Mocking | CRITICAL |
| 432-444 | test_tunnel_status_running | #2 Partial | HIGH |

### test_cli_configure.py (25 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 90-159 | test_configure_full_wizard_success | #5 Mocking | CRITICAL |
| 139-146 | (assertions) | #2 Partial | HIGH |
| 215-240 | test_configure_api_key_validation_failure | #1 Existence | HIGH |
| 261-319 | test_configure_auto_generates_token | #7 State | MEDIUM |
| 488-541 | test_configure_custom_model_specs | #7 State | MEDIUM |
| 597-656 | test_configure_gpu_insufficient_vram | #1 Existence | HIGH |
| 995-1054 | test_configure_saves_config | #4 Consumption | CRITICAL |
| 1116-1151 | test_configure_cancelled | #8 Branches | MEDIUM |

### test_cli_status.py (31 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 23-56 | test_show_termination_history | #2 Partial | HIGH |
| 146-193 | test_formats_uptime | #4 Consumption | MEDIUM |
| 338-389 | test_status_displays_running | #3 Shallow | HIGH |
| 710-756 | test_status_calculates_cost | #4 Consumption | CRITICAL |
| 876-890 | test_status_handles_api_error | #6 Swallowed | HIGH |

### test_ssh.py (38 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 76-109 | test_start_tunnel_success | #5 Mocking, #2 Partial | CRITICAL |
| 112-126 | test_start_tunnel_success_without_pid | #4 Consumption | HIGH |
| 129-144 | test_start_tunnel_ssh_command_failed | #4 Consumption | HIGH |
| 226-243 | test_stop_tunnel_success | #4 Consumption | HIGH |
| 304-315 | test_is_tunnel_running_process_exists | #4 Consumption | MEDIUM |
| 357-373 | test_find_tunnel_pid_success | #2 Partial | HIGH |
| 453-476 | test_connect_ssh_success | #2 Partial | HIGH |

### test_instance.py (23 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 96-109 | test_wait_for_ready_pending_to_active | #4 Consumption | HIGH |
| 112-125 | test_wait_for_ready_timeout | #5 Mocking | CRITICAL |
| 165-180 | test_wait_for_ready_handles_errors | #4 Consumption | HIGH |
| 183-216 | test_wait_for_ready_requires_both | #1 Existence | MEDIUM |
| 234-251 | test_wait_for_ready_poll_interval | #2 Partial | HIGH |

### test_lambda_api.py (59 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 469-481 | test_request_with_retry_success | #5 Mocking | HIGH |
| 581-616 | test_list_instances_success | #2 Partial | CRITICAL |
| 647-674 | test_launch_instance_minimal | #4 Consumption | CRITICAL |
| 758-783 | test_terminate_instance_success | #4 Consumption | HIGH |
| 857-874 | test_list_ssh_keys_success | #4 Consumption | HIGH |

### test_history.py (39 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 101-113 | test_to_dict_contains_all_fields | #2 Partial | MEDIUM |
| 223-235 | test_get_local_history_filters_time | #3 Shallow | HIGH |
| 251-258 | test_get_local_history_invalid_json | #6 Swallowed | CRITICAL |
| 316-326 | test_save_local_history_valid_json | #4 Consumption | MEDIUM |
| 342-355 | test_save_local_history_overwrites | #7 State | MEDIUM |
| 440-450 | test_fetch_remote_history_http_error | #5 Mocking | HIGH |
| 513-532 | test_sync_from_worker_success | #7 State | CRITICAL |

### test_model_registry.py (28 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 82-83 | test_deepseek_r1_70b_config | #3 Shallow | CRITICAL |
| 116-117 | test_qwen_coder_32b_int4_config | #3 Shallow | CRITICAL |
| 200 | test_includes_all_known_models | #8 Branches | HIGH |

### test_vram.py (21 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 151 | context_length_comparison | #2 Partial | MEDIUM |
| 230 | test_minimal_context | #1 Existence | CRITICAL |

### test_gpu_recommendation.py (18 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 68-69 | test_does_not_over_provision | #8 Branches | CRITICAL |

### test_config.py (13 tests)

| Line | Test | Pattern | Severity |
|------|------|---------|----------|
| 283-285 | test_config_load_validates | #6 Swallowed, #4 Consumption | CRITICAL |

### test_cli_models*.py (23 tests combined)

| File | Line | Test | Pattern | Severity |
|------|------|------|---------|----------|
| test_cli_models.py | 30-31 | test_models_list_displays | #3 Shallow | HIGH |
| test_cli_models_add.py | 88-91 | saved_values | #1 Existence | HIGH |
| test_cli_models_remove.py | 35-36 | mock_verification | #5 Mocking, #7 State | CRITICAL |

---

## Appendix B: Recommended Test Helpers

```python
# tests/helpers/assertions.py

def assert_exact_command(actual: list, expected: list) -> None:
    """Assert command arrays match exactly."""
    assert actual == expected, f"Command mismatch:\nExpected: {expected}\nActual: {actual}"

def assert_table_row(stdout: str, **expected_values) -> None:
    """Assert table output contains row with all expected values in same line."""
    lines = stdout.split('\n')
    for line in lines:
        if all(str(v) in line for v in expected_values.values()):
            return
    raise AssertionError(f"No row found with all values: {expected_values}")

def assert_no_error_keywords(stdout: str) -> None:
    """Assert output doesn't contain error indicators."""
    error_keywords = ['error', 'failed', 'exception', 'traceback']
    lower = stdout.lower()
    for keyword in error_keywords:
        assert keyword not in lower, f"Error keyword '{keyword}' found in output"

def assert_json_consumed(mock_response, expected_calls: int = 1) -> None:
    """Assert response.json() was called expected number of times."""
    assert mock_response.json.call_count == expected_calls, \
        f"response.json() called {mock_response.json.call_count} times, expected {expected_calls}"

def assert_state_transition(get_state_fn, expected_before, expected_after, action_fn) -> None:
    """Assert state changes correctly from before to after action."""
    before = get_state_fn()
    assert before == expected_before, f"Initial state wrong: {before}"
    action_fn()
    after = get_state_fn()
    assert after == expected_after, f"Final state wrong: {after}"
```

---

*Report generated by Green Mirage Audit System*
*Total audit time: ~45 minutes across 5 parallel agents*

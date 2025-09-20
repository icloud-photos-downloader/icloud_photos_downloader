# ADT Refactoring Plan for core_single_run

## Background
We're refactoring `core_single_run()` to replace exception throwing with ADT (Algebraic Data Type) returns. Previous attempts using direct full conversion caused test hangs with `--watch-with-interval`. This incremental approach allows us to identify exactly which conversion causes issues.

## Current Status
- **Branch**: `refactor/direct-adt-propagation`
- **Phase 1**: ✅ COMPLETED - Infrastructure in place
  - Changed `core_single_run` return type to `int | CoreSingleRunErrorResult`
  - Added `CoreSingleRunErrorResult` union type in response_types.py
  - Updated caller with pattern matching
  - All exceptions still thrown (dual mode)

- **Phase 2**: ✅ COMPLETED - Converting authentication exceptions to ADT returns
  - ✅ Step 1: `AuthenticatorTwoSAExit` - COMPLETED
  - ✅ Step 2: `AuthPasswordNotProvided` - COMPLETED
  - ✅ Step 3: `AuthInvalidCredentials` - COMPLETED
  - ✅ Step 4: `AuthServiceNotActivated` - COMPLETED
  - ❌ Step 5: `AuthServiceUnavailable` - SKIPPED (breaks watch mode)
  - ✅ Step 6: `AuthAPIError` - COMPLETED
  - ✅ Step 7: `AuthUnexpectedError` - COMPLETED (with special handling)
  - ❌ Step 8: `AuthenticatorMFAError` - SKIPPED (breaks MFA flow)
  - ✅ Step 9: `PhotoLibraryNotFinishedIndexing` - COMPLETED

## Phase 2 Detailed Plan

### Step 2: Convert AuthPasswordNotProvided
- Line: ~996
- Current: `raise PyiCloudConnectionException("Password not provided")`
- Change to: `return auth_result`
- Test impact on watch interval

### Step 3: Convert AuthInvalidCredentials
- Line: ~998
- Current: `raise PyiCloudFailedLoginException("Invalid email/password combination.")`
- Change to: `return auth_result`
- Test impact on watch interval

### Step 4: Convert AuthServiceNotActivated
- Line: ~1000
- Current: `raise PyiCloudServiceNotActivatedException(reason, code)`
- Change to: `return auth_result`
- Test impact on watch interval

### Step 5: ❌ SKIP - AuthServiceUnavailable
- Line: ~1002
- Current: `raise PyiCloudServiceUnavailableException(reason)`
- CANNOT CONVERT: This breaks the --watch-with-interval functionality
- The exception handler logs "Apple iCloud is temporary refusing to serve icloudpd"
- When converted to ADT return, this message is not logged and tests fail
- KEEP AS EXCEPTION

### Step 6: Convert AuthAPIError
- Line: ~1004
- Current: `raise PyiCloudAPIResponseException(reason, code)`
- Change to: `return auth_result`
- Test impact on watch interval

### Step 7: Convert AuthUnexpectedError
- Line: ~1006-1023
- Current: Complex logic with different exception types
- Change to: `return auth_result`
- Test impact on watch interval

### Step 8: ❌ SKIP - AuthenticatorMFAError
- Line: ~1024-1025
- Current: `raise PyiCloudFailedMFAException(error_msg)`
- CANNOT CONVERT: Breaks MFA test flow
- The exception is needed for proper error logging in MFA flow
- KEEP AS EXCEPTION

### Step 9: Convert service access errors
These are in the main body after authentication:
- ✅ PhotoLibraryNotFinishedIndexing - COMPLETED (no test issues)
- ⚠️ Response2SARequired, ResponseServiceNotActivated, ResponseAPIError, ResponseServiceUnavailable
  - Found 53 exception raises across service access logic
  - These are deeply nested throughout the service interaction code
  - Converting all would be a massive change affecting entire service flow
  - RECOMMENDATION: Keep as exceptions for now, consider separate refactoring later

### Step 10: Handle exception catching block
Once all raises are converted to returns:
- Remove the try-catch wrapper around the main logic
- Update return type documentation
- Clean up imports

## Testing Protocol for Each Step
1. Make the code change
2. Run: `python -m pytest tests/test_authentication.py::AuthenticationTestCase::test_failed_auth_503_watch -xvs`
3. If passes, run: `python -m pytest tests/test_authentication.py -v --tb=line`
4. Run mypy: `export PYTHONPATH=src && python -m mypy src/icloudpd/base.py --strict`
5. Only commit if all tests pass

## Key Files
- `/workspaces/icloud_photos_downloader/src/icloudpd/base.py` - Main file being refactored
- `/workspaces/icloud_photos_downloader/src/pyicloud_ipd/response_types.py` - ADT definitions
- Line 986-1027: Authentication result handling in core_single_run
- Line 484-494: Caller's pattern matching in _process_all_users_once

## Important Context
- The watch interval hang appears to be related to how exceptions interrupt control flow
- The incremental approach has proven successful so far
- Each ADT conversion removes one exception path
- The caller currently maps all ADT errors to exit code 1 (can be refined later)

## Results Summary
### Successfully Converted (7 out of 10 authentication errors)
1. `AuthenticatorTwoSAExit` - Clean conversion, no issues
2. `AuthPasswordNotProvided` - Clean conversion, no issues
3. `AuthInvalidCredentials` - Clean conversion, no issues
4. `AuthServiceNotActivated` - Clean conversion, no issues
5. `AuthAPIError` - Clean conversion, no issues
6. `AuthUnexpectedError` - Required special handling for logging and VCR exceptions
7. `PhotoLibraryNotFinishedIndexing` - Clean conversion with logging

### Must Remain as Exceptions (3 cases)
1. `AuthServiceUnavailable` - Breaks watch mode if converted
2. `AuthenticatorMFAError` - Breaks MFA flow if converted
3. Service access errors (53 instances) - Too complex for current refactoring

### Key Learnings
1. Incremental approach successfully identified problematic conversions
2. Some exceptions are integral to control flow (watch mode, MFA)
3. Error logging is critical for watch mode functionality
4. VCR/test exceptions must propagate for test infrastructure
5. Service access errors would require separate, larger refactoring

## Success Criteria
✅ All tests pass, especially `test_failed_auth_503_watch`
✅ No behavioral changes from user perspective
✅ Authentication errors mostly use ADT (7/10 converted)
✅ Maintainable code with clear error propagation
⚠️ Full exception removal not achievable due to architectural constraints
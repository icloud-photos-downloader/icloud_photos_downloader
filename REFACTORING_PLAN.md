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

- **Phase 2**: IN PROGRESS - Converting exceptions to ADT returns
  - ✅ Step 1: `AuthenticatorTwoSAExit` - COMPLETED (no test issues)
  - 🔄 Step 2: Simple authentication errors - NEXT

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

### Step 5: Convert AuthServiceUnavailable
- Line: ~1002
- Current: `raise PyiCloudServiceUnavailableException(reason)`
- Change to: `return auth_result`
- Test impact on watch interval

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

### Step 8: Convert AuthenticatorMFAError
- Line: ~1024-1025
- Current: `raise PyiCloudFailedMFAException(error_msg)`
- Change to: `return auth_result`
- Test impact on watch interval

### Step 9: Convert service access errors
These are in the main body after authentication:
- PhotoLibraryNotFinishedIndexing
- Response2SARequired in various places
- ResponseServiceNotActivated in various places
- ResponseAPIError in various places
- ResponseServiceUnavailable in various places

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

## Success Criteria
- All tests pass, especially `test_failed_auth_503_watch`
- No behavioral changes from user perspective
- Clean ADT-based error handling without exception wrapping
- Maintainable code with clear error propagation
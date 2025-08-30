# Dependency Injection and Functional Composition Refactoring

## Summary
This refactoring series implements dependency injection patterns and functional composition throughout the icloud_photos_downloader codebase, removing tight coupling between service layers and improving testability.

## Completed Refactorings

### 1. Extract Fingerprint Hash Logic from calculate_filename()
**Commit**: `caf2a92 - Extract fingerprint hash logic from calculate_filename() into separate fallback function`

**Changes**:
- Made `calculate_filename()` return `Optional[str]` (None when filenameEnc missing)
- Created `generate_fingerprint_filename()` for fallback logic
- Created `bind_filename_with_fallback()` to handle None returns
- Updated all callers to use binding pattern

**Pattern**: Optional/Maybe pattern with fallback composition

### 2. Extract raw_policy from PyiCloudService
**Commit**: `ad452c3 - Extract raw_policy from PyiCloudService using dependency injection pattern`

**Changes**:
- Removed `raw_policy` parameter from PyiCloudService and PhotosService constructors
- Created `apply_raw_policy()` standalone function
- Added `versions_with_raw_policy()` method to PhotoAsset
- Updated all callers to pass `raw_policy` explicitly
- Updated download_builder signature to include raw_policy parameter

**Pattern**: Dependency injection - pass parameters explicitly instead of storing in service

### 3. Implement fromMaybe Function (Haskell-style)
**Commit**: `a6f362c - Implement fromMaybe function and replace bind_filename_with_fallback with functional composition`

**Changes**:
- Created `foundation.core.optional.fromMaybe()` function similar to Haskell's fromMaybe
- Replaced `bind_filename_with_fallback` with `filename_with_fallback` using fromMaybe
- Applied functional composition pattern: `fromMaybe(default)(maybe_value)`

**Pattern**: Functional composition with Higher-Order Functions

### 4. Extract Download Function from PhotoAsset
**Commit**: `0344d94 - refactor: use base Session class instead of PyiCloudSession in PhotoAsset.download`

**Changes**:
- Created standalone `download_asset()` function taking session parameter
- Updated `PhotoAsset.download()` to accept session parameter
- Removed service dependency from PhotoAsset constructor
- Used base `Session` class instead of `PyiCloudSession` for better abstraction
- Fixed all test mock functions to match new signatures

**Pattern**: Dependency injection + Interface Segregation (using base Session type)

### 5. Extract Service Dependencies from PhotoLibrary and PhotoAlbum
**Commit**: `26c96b2 - refactor: extract service dependencies from PhotoLibrary and PhotoAlbum constructors`

**Changes**:
- Updated PhotoLibrary constructor: `(service, zone_id, library_type)` → `(service_endpoint, params, session, zone_id, library_type)`
- Updated PhotoAlbum constructor: `(service, service_endpoint, ...)` → `(params, session, service_endpoint, ...)`
- Updated all callers to pass dependencies explicitly
- Fixed PhotosService inheritance with proper parent constructor
- Updated base.py to use direct properties instead of `service.*`

**Pattern**: Constructor Dependency Injection

## Key Patterns Implemented

### 1. **Dependency Injection**
- **Before**: Classes stored entire service objects and accessed nested properties
- **After**: Classes receive only the specific dependencies they need
- **Benefits**: Better testability, reduced coupling, clearer dependencies

### 2. **Functional Composition**
- **Before**: Imperative if/else logic for handling optional values
- **After**: Functional composition with higher-order functions like `fromMaybe`
- **Benefits**: More declarative code, better composability

### 3. **Optional/Maybe Pattern**
- **Before**: Methods threw exceptions or returned default values internally
- **After**: Methods return `Optional[T]` and callers handle None explicitly
- **Benefits**: Explicit error handling, no hidden defaults

### 4. **Interface Segregation**
- **Before**: Depended on concrete `PyiCloudSession` class
- **After**: Depend on base `Session` interface from requests library
- **Benefits**: More flexible, easier to mock in tests

## Architecture Impact

### Service Layer Decoupling
```
Before: PyiCloudService → PhotosService → PhotoLibrary → PhotoAlbum → PhotoAsset
        (Tight coupling - each layer stores references to parent services)

After:  PyiCloudService → PhotosService → PhotoLibrary → PhotoAlbum → PhotoAsset
        (Loose coupling - dependencies passed explicitly as needed)
```

### Parameter Flow
```
Before: raw_policy stored in PyiCloudService, accessed via service.raw_policy
After:  raw_policy passed explicitly: download_builder(raw_policy, ...) → photo.versions_with_raw_policy(raw_policy)

Before: session accessed via PhotoAsset.service.session
After:  session passed explicitly: photo.download(session, url, start)

Before: PhotoLibrary accesses service.params, service.session, service.get_service_endpoint()  
After:  PhotoLibrary receives params, session, service_endpoint directly
```

## Quality Metrics

- **Tests**: All 203 tests pass (200 passed, 3 skipped)
- **Type Safety**: mypy strict mode passes on 73 files (src + tests)
- **Code Quality**: ruff linting passes with no issues
- **Formatting**: ruff format applied consistently

## File Changes Summary

### Core Service Files
- `src/pyicloud_ipd/services/photos.py` - Major refactoring of PhotoAsset, PhotoLibrary, PhotoAlbum, PhotosService
- `src/pyicloud_ipd/base.py` - Updated PyiCloudService and download_builder
- `src/icloudpd/base.py` - Updated callers to use new dependency injection patterns
- `src/icloudpd/download.py` - Updated to pass session explicitly to PhotoAsset.download()

### Foundation Layer
- `src/foundation/core/optional/__init__.py` - Added fromMaybe function for functional composition

### Test Files
- `tests/test_download_photos.py` - Updated mock functions for new PhotoAsset.download signature
- `tests/test_download_photos_id.py` - Updated mock functions for new PhotoAsset.download signature

## Parameters Passed to PhotosService
PhotosService receives params from PyiCloudService (initially empty dict) and adds:
```python
{
    'remapEnums': True,         # Tells iCloud API to remap enumeration values
    'getCurrentSyncToken': True  # Requests current synchronization token
}
```

These params are used in `urlencode(params)` for building iCloud API query strings throughout the photo library operations.

## Migration Guide for Future Development

### Adding New Dependencies
1. **Identify the minimal dependency needed** (not entire service objects)
2. **Pass dependencies through constructor parameters**
3. **Update all callers** to provide the dependency explicitly
4. **Write tests** that can mock the dependency easily

### Following the Patterns
1. **Use Optional[T] return types** for methods that might not find results
2. **Use fromMaybe()** for providing defaults to Optional values
3. **Pass session parameters explicitly** instead of storing in services
4. **Use base interface types** (like Session) instead of concrete implementations

This refactoring establishes a foundation for more maintainable, testable, and loosely-coupled code following functional programming and dependency injection principles.
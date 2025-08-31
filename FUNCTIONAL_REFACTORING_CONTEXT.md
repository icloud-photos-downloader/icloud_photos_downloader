# Functional Programming Refactoring Context

## Objective
Refactor codebase to use point-free style with functional composition and partial application, separating pure and side-effectful functionality into separate functions.

## Current State Analysis

### Existing Functional Infrastructure
- ✅ Excellent foundation in `src/foundation/core/` with composition, partial application, and point-free utilities
- ✅ Some good examples already exist:
  - `unique_sequence` in `foundation/__init__.py` (lines 133-135)
  - `compose(filename_cleaner, clean_filename)` in `pyicloud_ipd/services/photos.py` (line 75)

### Identified Refactoring Opportunities

#### 1. String Processing Functions (High Priority)
**Location**: Multiple files using `.strip()`, `.lower()`, `.endswith()` inline
**Problem**: Mixed string operations scattered throughout codebase
**Solution**: Create reusable point-free string utilities

#### 2. Filename Generation Functions (High Priority)
**Location**: `src/icloudpd/base.py:108-119` (`lp_filename_*` functions)
**Problem**: Imperative conditionals mixed with string operations
**Solution**: Use functional composition for cleaner logic

#### 3. Input Validation Chains (High Priority) 
**Location**: `src/icloudpd/authentication.py:149-150`, others
**Problem**: Chained method calls mixing I/O and transformations
**Solution**: Separate I/O from pure transformations

#### 4. Configuration Processing (Medium Priority)
**Location**: `src/icloudpd/cli.py:282-284`
**Problem**: Imperative if/elif chains for lookups
**Solution**: Functional lookup patterns with composition

#### 5. Download Logic Separation (Medium Priority)
**Location**: `src/icloudpd/base.py:584+` (`download_builder`)
**Problem**: Mixed I/O and business logic in large functions
**Solution**: Extract pure calculations from side-effectful operations

## Implementation Plan

### Phase 1: Foundation Extensions
1. Create `src/foundation/string.py` with point-free string utilities
2. Create `src/foundation/predicates.py` with boolean composition utilities
3. Extend existing functional utilities as needed

### Phase 2: High-Priority Refactoring
1. Refactor `lp_filename_*` functions using composition
2. Extract string processing chains into composed functions
3. Separate I/O from validation logic in authentication

### Phase 3: Medium-Priority Refactoring
1. Replace imperative lookups with functional patterns
2. Separate pure calculations from I/O in download logic
3. Refactor configuration processing

## Success Criteria
- ✅ All tests pass after each refactoring step
- ✅ Code passes formatting, linting, and strict mypy
- ✅ Improved separation of pure vs side-effectful functions
- ✅ Increased use of point-free composition
- ✅ Better testability and reusability

## New Utilities to Create

### String Utilities (`src/foundation/string.py`)
- `strip(s: str) -> str`
- `endswith(suffix: str) -> Callable[[str], bool]`
- `startswith(prefix: str) -> Callable[[str], bool]`
- `contains(substring: str) -> Callable[[str], bool]`
- `eq(expected: str) -> Callable[[str], bool]`

### Predicate Utilities (`src/foundation/predicates.py`)
- `and_(f1, f2) -> Callable[[T], bool]`
- `or_(f1, f2) -> Callable[[T], bool]`
- `not_(f) -> Callable[[T], bool]`

## Benefits Expected
- Better testability (pure functions easier to unit test)
- Increased reusability through composition
- Clearer separation of concerns
- More maintainable code through point-free style
- Reduced coupling between I/O and business logic
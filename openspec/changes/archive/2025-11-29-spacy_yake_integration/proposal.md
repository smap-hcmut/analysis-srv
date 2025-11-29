# SpaCy-YAKE Integration

## Why

The Analytics Engine currently has PhoBERT for sentiment analysis but lacks keyword extraction capabilities. SpaCy-YAKE code has been copied into the project but needs refactoring to:

1. **Match Project Structure** - Align with established patterns (like PhoBERT integration)
2. **Configuration Management** - Move hard-coded values to config/environment
3. **Testing** - Complete comprehensive test suite
4. **Documentation** - Update project docs and README

## What Changes

### Code Refactoring
- Restructure `infrastructure/spacyyake/` to match `infrastructure/ai/` pattern
- Create clean interface similar to PhoBERT wrapper
- Extract constants to configuration file
- Add proper error handling and logging

### Configuration
- Add SpaCy-YAKE settings to `core/config.py`
- Update `.env.example` with new environment variables
- Create `infrastructure/ai/spacyyake_constants.py`

### Testing
- Complete unit tests in `tests/spacyyake/`
- Add integration tests
- Add performance benchmarks
- Ensure 100% test coverage

### Documentation
- Update `README.md` with SpaCy-YAKE usage
- Update `openspec/project.md`
- Create model report similar to `phobert_report.md`

## User Review Required

> [!IMPORTANT]
> This refactoring will NOT change the core SpaCy-YAKE algorithm logic. Only structural and configuration changes to fit project standards.

> [!WARNING]
> The existing test file (`tests/test_aspect_mapper.py`) references old paths (`src.core.utils.aspect_mapper`). These will be updated to match new structure.

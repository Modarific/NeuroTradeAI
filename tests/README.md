# NeuroTradeAI Test Suite

This directory contains comprehensive tests for the NeuroTradeAI real-time trading data scraper.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest configuration and fixtures
├── test_storage.py          # Storage component unit tests
├── test_rate_limiter.py     # Rate limiter unit tests
├── test_adapters.py         # Adapter unit tests
├── test_integration.py      # End-to-end integration tests
├── test_load.py             # Performance and load tests
├── test_security.py         # Security and credential tests
└── README.md                # This file
```

## Test Categories

### 1. Unit Tests
- **Storage Tests** (`test_storage.py`): Test data storage, retrieval, and persistence
- **Rate Limiter Tests** (`test_rate_limiter.py`): Test rate limiting functionality
- **Adapter Tests** (`test_adapters.py`): Test individual adapter components

### 2. Integration Tests
- **End-to-End Workflow** (`test_integration.py`): Test complete data flows from source to storage
- **Concurrent Operations**: Test multiple adapters running simultaneously
- **Data Persistence**: Test data survival across restarts

### 3. Load Tests
- **Performance Testing** (`test_load.py`): Test system performance under high load
- **Rate Limiting**: Test rate limiter behavior under concurrent requests
- **Storage Performance**: Test storage operations with large datasets
- **Memory Usage**: Test memory efficiency under load

### 4. Security Tests
- **Credential Security** (`test_security.py`): Test encryption and credential protection
- **Data Validation**: Test input sanitization and validation
- **SQL Injection Protection**: Test protection against malicious inputs
- **Path Traversal Protection**: Test protection against directory traversal attacks

## Running Tests

### Prerequisites
```bash
pip install -r requirements-test.txt
```

### Basic Test Execution
```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --type unit
python run_tests.py --type integration
python run_tests.py --type load
python run_tests.py --type security

# Run with verbose output
python run_tests.py --verbose

# Run with coverage report
python run_tests.py --coverage
```

### Direct Pytest Execution
```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/test_storage.py
pytest tests/test_integration.py

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run in parallel
pytest tests/ -n auto
```

## Test Fixtures

The test suite includes several useful fixtures defined in `conftest.py`:

- `temp_dir`: Creates temporary directories for test data
- `test_storage`: Creates a test storage manager
- `test_rate_limiter`: Creates a test rate limiter
- `mock_vault`: Creates a mock credential vault
- `sample_ohlcv_data`: Sample OHLCV data for testing
- `sample_news_data`: Sample news data for testing
- `sample_filing_data`: Sample filing data for testing

## Test Coverage

The test suite aims for comprehensive coverage of:

- ✅ **Storage Operations**: All storage methods and edge cases
- ✅ **Rate Limiting**: Token bucket algorithm and burst capacity
- ✅ **Data Adapters**: All adapter types and error conditions
- ✅ **Integration Flows**: Complete data pipelines
- ✅ **Performance**: Load testing and concurrent operations
- ✅ **Security**: Credential protection and input validation

## Continuous Integration

The test suite is designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    pip install -r requirements-test.txt
    python run_tests.py --coverage
```

## Test Data

Tests use synthetic data to avoid dependencies on external APIs:

- **OHLCV Data**: Mock price and volume data
- **News Data**: Mock news articles with sentiment scores
- **Filing Data**: Mock SEC filing information
- **API Responses**: Mock HTTP responses for all external services

## Performance Benchmarks

The load tests establish performance benchmarks:

- **Storage**: 1000+ records per second
- **Rate Limiting**: 100+ concurrent requests
- **Memory Usage**: <100MB for 10,000 records
- **Query Performance**: <2 seconds for 5000 records

## Security Validation

Security tests validate:

- **Encryption**: All credentials encrypted at rest
- **Input Validation**: Malicious input handling
- **SQL Injection**: Protection against injection attacks
- **Path Traversal**: Protection against directory traversal
- **Data Sanitization**: Proper data cleaning and validation

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the app directory is in the Python path
2. **Async Test Failures**: Use `pytest-asyncio` for async test support
3. **Permission Errors**: Ensure test directories are writable
4. **Memory Issues**: Reduce test dataset sizes for low-memory environments

### Debug Mode

Run tests with debug output:
```bash
pytest tests/ -v -s --tb=short
```

### Test Isolation

Each test is isolated and doesn't depend on others:
- Temporary directories are created and cleaned up
- Mock objects are used for external dependencies
- No shared state between tests

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Use appropriate fixtures from `conftest.py`
3. Include both positive and negative test cases
4. Add docstrings explaining test purpose
5. Ensure tests are isolated and repeatable

## Test Reports

After running tests with coverage, view the HTML report:
```bash
open htmlcov/index.html
```

This provides detailed coverage information for all modules.

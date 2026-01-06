# Contributing to Clariona Backend

Thank you for your interest in contributing to the Clariona Backend! This document provides guidelines and instructions for contributing.

---

## 📋 Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing Requirements](#testing-requirements)
6. [Pull Request Process](#pull-request-process)
7. [Code Review Guidelines](#code-review-guidelines)

---

## Code of Conduct

### Our Standards

- **Be Respectful**: Treat everyone with respect and kindness
- **Be Collaborative**: Work together to build the best solution
- **Be Professional**: Maintain professional communication
- **Be Open**: Welcome new ideas and different perspectives

### Reporting Issues

If you encounter any issues or have concerns, please report them through the appropriate channels.

---

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Git
- Familiarity with FastAPI, SQLAlchemy, and Python best practices

### Setup Development Environment

1. **Fork and Clone**:
```bash
git clone <your-fork-url>
cd Clariona-Backend
```

2. **Create Virtual Environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

4. **Setup Environment Variables**:
```bash
cp .env.example .env
# Edit .env with your development configuration
```

5. **Run Database Migrations**:
```bash
alembic upgrade head
```

6. **Run Tests**:
```bash
pytest tests/
```

---

## Development Workflow

### Branch Naming

Use descriptive branch names:
- `feature/add-new-collector` - New features
- `fix/fix-config-loading` - Bug fixes
- `refactor/improve-error-handling` - Refactoring
- `docs/update-architecture-docs` - Documentation

### Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

**Examples**:
```
feat(collectors): add new Twitter collector

Add support for collecting Twitter data using new API endpoint.
Includes rate limiting and error handling.

Closes #123
```

```
fix(config): fix ConfigManager path resolution

Fix issue where ConfigManager was not resolving paths correctly
on Windows systems.

Fixes #456
```

### Development Process

1. **Create Branch**:
```bash
git checkout -b feature/your-feature-name
```

2. **Make Changes**:
   - Follow coding standards
   - Write tests
   - Update documentation

3. **Test Changes**:
```bash
pytest tests/
python tests/test_manual_cycle.py  # If applicable
```

4. **Commit Changes**:
```bash
git add .
git commit -m "feat(scope): your commit message"
```

5. **Push and Create PR**:
```bash
git push origin feature/your-feature-name
# Create pull request on GitHub
```

---

## Coding Standards

### General Guidelines

- **Follow PEP 8**: Python style guide
- **Type Hints**: Always include type hints for function signatures
- **Docstrings**: Add docstrings to all public functions and classes
- **Line Length**: Maximum 120 characters (soft limit)

### Import Order

Follow this standard import order:

```python
# 1. Standard library
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 2. Third-party
from fastapi import FastAPI
from sqlalchemy.orm import Session

# 3. Local - config
from src.config.config_manager import ConfigManager
from src.config.path_manager import PathManager
from src.config.logging_config import get_logger

# 4. Local - exceptions
from exceptions import ConfigError, ProcessingError

# 5. Local - utils
from src.utils.common import parse_datetime

# 6. Local - processing/agent/api
from src.processing.data_processor import DataProcessor
```

### Configuration

**Always use ConfigManager**:
```python
from src.config.config_manager import ConfigManager

config = ConfigManager()
timeout = config.get_int('collectors.twitter.timeout', 300)

# ✅ Good - uses ConfigManager
# ❌ Bad - hardcoded: timeout = 300
```

### Path Management

**Always use PathManager**:
```python
from src.config.path_manager import PathManager

paths = PathManager()
data_dir = paths.data_raw

# ✅ Good - uses PathManager
# ❌ Bad - hardcoded: data_dir = Path("data/raw")
```

### Error Handling

**Always use custom exceptions**:
```python
from exceptions import ConfigError, ProcessingError

# ✅ Good
if not config_path.exists():
    raise ConfigError(f"Config file not found: {config_path}")

# ❌ Bad
if not config_path.exists():
    raise ValueError(f"Config file not found: {config_path}")
```

### Logging

**Always use centralized logging**:
```python
from src.config.logging_config import get_logger

logger = get_logger(__name__)
logger.info("Processing started")

# ✅ Good - uses centralized logging
# ❌ Bad - direct logging: logging.info("Processing started")
```

### Type Hints

**Always include type hints**:
```python
from typing import List, Dict, Any, Optional

def process_data(
    data: List[Dict[str, Any]],
    config: Optional[ConfigManager] = None
) -> Dict[str, Any]:
    """
    Process data with optional configuration.
    
    Args:
        data: List of data records
        config: Optional ConfigManager instance
    
    Returns:
        Processed data dictionary
    """
    pass
```

### Docstrings

**Use Google-style docstrings**:
```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of the function.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception is raised
    """
    pass
```

---

## Testing Requirements

### Test Coverage

- **New Features**: Must include tests
- **Bug Fixes**: Must include tests that verify the fix
- **Refactoring**: Should maintain or improve test coverage

### Writing Tests

**Test Structure**:
```python
import pytest
from src.config.config_manager import ConfigManager

class TestConfigManager:
    def test_get_int(self):
        """Test getting integer configuration value."""
        config = ConfigManager()
        value = config.get_int('processing.parallel.max_collector_workers', 8)
        assert value == 8
    
    def test_get_with_default(self):
        """Test getting configuration with default value."""
        config = ConfigManager()
        value = config.get('non.existent.key', 'default')
        assert value == 'default'
```

### Running Tests

**All Tests**:
```bash
pytest tests/
```

**Specific Test File**:
```bash
pytest tests/test_config_manager.py
```

**With Coverage**:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Test Organization

- **Unit Tests**: `tests/test_*.py` - Test individual functions/classes
- **Integration Tests**: `tests/test_integration.py` - Test component interactions
- **Manual Tests**: `tests/test_manual_*.py` - Manual verification scripts

---

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
```bash
pytest tests/
```

2. **Check Code Style**: Ensure code follows PEP 8
```bash
# Use your IDE's linter or flake8
flake8 src/
```

3. **Type Checking** (Optional):
```bash
mypy src/
```

4. **Update Documentation**: Update relevant documentation
   - `BACKEND_ARCHITECTURE.md` - If architecture changes
   - `DEVELOPER_GUIDE.md` - If developer patterns change
   - `MIGRATION_GUIDE.md` - If breaking changes
   - Code docstrings - Always update

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally
```

### Review Process

1. **Automated Checks**: CI/CD will run tests and checks
2. **Code Review**: At least one maintainer will review
3. **Feedback**: Address any feedback or requested changes
4. **Approval**: Once approved, PR will be merged

---

## Code Review Guidelines

### For Contributors

- **Be Open to Feedback**: Welcome constructive criticism
- **Respond Promptly**: Address review comments in a timely manner
- **Be Professional**: Maintain professional communication
- **Ask Questions**: Don't hesitate to ask for clarification

### For Reviewers

- **Be Constructive**: Provide helpful, actionable feedback
- **Be Respectful**: Maintain respectful and professional tone
- **Be Specific**: Point out specific issues with code examples
- **Be Timely**: Review PRs in a reasonable timeframe

### Review Checklist

- [ ] Code follows style guidelines
- [ ] Type hints are included
- [ ] Docstrings are present and accurate
- [ ] Tests are included and pass
- [ ] Configuration uses ConfigManager
- [ ] Paths use PathManager
- [ ] Error handling uses custom exceptions
- [ ] Logging uses centralized logging
- [ ] Documentation is updated
- [ ] No hardcoded values
- [ ] No security issues

---

## Additional Resources

- `DEVELOPER_GUIDE.md` - Comprehensive developer guide
- `BACKEND_ARCHITECTURE.md` - Architecture documentation
- `MIGRATION_GUIDE.md` - Migration guide
- `cleanup/README.md` - Cleanup progress and standards

---

## Questions?

If you have questions or need help:

1. Check the documentation
2. Search existing issues
3. Create a new issue with your question
4. Reach out to maintainers

---

**Thank you for contributing to Clariona Backend!** 🎉

---

**Last Updated**: 2025-01-02  
**Version**: 2.0









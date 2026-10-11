# Contributing to RPG Database Manager

Thank you for your interest in contributing to RPG Database Manager! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members
- Be open to constructive criticism

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git for version control
- Basic understanding of PyQt6
- Familiarity with SQLite databases

### First Contribution

If you're new to open source or this project:

1. Start with issues labeled `good-first-issue` or `help-wanted`
2. Read through the codebase to understand the structure
3. Check the [User Guide](docs/user_guide.md) to understand features
4. Review the [Quick Style Reference](QUICK_STYLE_REFERENCE.md) for UI guidelines

## Development Setup

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/rpg-database-manager.git
   cd rpg-database-manager
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   # Install all dependencies including the test tools
   pip install -r requirements.txt
   ```
   Release builds install from the hashed lock files (`requirements-windows.lock`, `requirements-linux.lock`,
   `pip install --require-hashes`). After changing `requirements.txt`, run `tools/update-locks.sh` and commit the locks.
   ```bash
   ```

4. **Run the Application**
   ```bash
   python main.py
   ```

5. **Run Tests**
   ```bash
   pytest
   ```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug Fixes**: Fix issues in existing code
- **New Features**: Implement new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **UI/UX**: Enhance user interface and experience
- **Performance**: Optimize code for better performance
- **Refactoring**: Improve code quality without changing functionality

### Contribution Workflow

1. **Create an Issue** (if one doesn't exist)
   - Describe the bug or feature
   - Explain why this change is needed
   - Discuss implementation approach

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make Your Changes**
   - Write clean, documented code
   - Follow coding standards
   - Add tests for new features
   - Update documentation as needed

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add feature: description of your changes"
   ```

   Commit message format:
   - `Add feature: <description>` for new features
   - `Fix: <description>` for bug fixes
   - `Update: <description>` for improvements
   - `Refactor: <description>` for code refactoring
   - `Docs: <description>` for documentation
   - `Test: <description>` for tests

5. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Go to the GitHub repository
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template
   - Link related issues

## Coding Standards

### Python Style Guide

Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guidelines:

- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use descriptive variable names
- Add docstrings to all functions and classes

### Code Formatting

Use Black for code formatting:

```bash
black .
```

### Type Hints

Use type hints for function parameters and return values:

```python
def create_document(title: str, content: str, entity_type: str) -> int:
    """
    Create a new document.

    Args:
        title: Document title
        content: Document content
        entity_type: Type of entity (NPC, Location, etc.)

    Returns:
        The ID of the created document
    """
    pass
```

### Code Quality

Run linters before committing:

```bash
# Flake8 for style checking
flake8 .

# Mypy for type checking
mypy .
```

### UI Development

When working on UI components:

- Use the design system from `gui/styles.py`
- Follow the [Quick Style Reference](QUICK_STYLE_REFERENCE.md)
- Use semantic color names, not hex codes
- Apply consistent spacing using the spacing system
- Add icons to improve UX
- Test in both Dark and Light themes

Example:
```python
from gui.styles import get_style_manager

style = get_style_manager()

# Good
button.setStyleSheet(style.primary_button_style())

# Avoid
button.setStyleSheet("background-color: #4a9eff;")
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models/test_crud.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Writing Tests

- Add tests for all new features
- Include edge cases and error handling
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern

Example:
```python
def test_create_document_with_valid_data():
    """Test creating a document with valid data."""
    # Arrange
    title = "Test NPC"
    content = "A test character"

    # Act
    doc_id = create_document(title, content, "NPC")

    # Assert
    assert doc_id > 0
    doc = get_document(doc_id)
    assert doc.title == title
```

### Test Coverage

Aim for:
- Minimum 70% overall coverage
- 90%+ coverage for critical paths
- 100% coverage for security-related code

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No merge conflicts with main branch

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Related Issues
Closes #123

## Testing
How to test these changes

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

### Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, your PR will be merged
4. Your contribution will be credited in the CHANGELOG

## Reporting Bugs

### Before Reporting

- Check if the bug has already been reported
- Try to reproduce the bug with the latest version
- Gather relevant information (OS, Python version, error messages)

### Bug Report Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Windows 10]
- Python Version: [e.g., 3.11]
- Application Version: [e.g., 1.0.0]

## Additional Context
Screenshots, logs, or other relevant information
```

## Feature Requests

We welcome feature suggestions! When requesting a feature:

1. Check if it has already been requested
2. Explain the problem it solves
3. Describe the proposed solution
4. Consider alternative approaches
5. Discuss potential implementation challenges

### Feature Request Template

```markdown
## Feature Description
Clear description of the feature

## Problem Statement
What problem does this solve?

## Proposed Solution
How should this work?

## Alternatives Considered
Other approaches you've thought about

## Additional Context
Mockups, examples, or references
```

## Project Structure

Understanding the codebase:

```
.
├── main.py                 # Application entry point
├── config/                 # Configuration modules
├── gui/                    # GUI components
│   ├── main_window.py     # Main application window
│   ├── components/        # Reusable UI components
│   ├── dialogs/           # Dialog windows
│   ├── widgets/           # Custom widgets
│   └── workers/           # Background workers
├── models/                 # Data models and database
├── services/              # Business logic
├── utils/                 # Utility functions
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Communication

- **Issues**: For bug reports and feature requests
- **Pull Requests**: For code contributions
- **Discussions**: For questions and general discussion

## Recognition

Contributors will be:
- Listed in the project README
- Credited in CHANGELOG.md
- Recognized in release notes

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to RPG Database Manager! Your efforts help make this tool better for the entire tabletop RPG community.

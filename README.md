# AutoCraft

### Playwright Test-Code Generation Desktop Application

AutoCraft is a Windows desktop application that simplifies the creation of Playwright-based test automation by combining browser recording, test-case identification, code generation and an integrated Python code editor into a single workflow.

The application uses **Playwright Codegen** to capture browser interactions and converts the recorded actions into pytest-compatible test functions that can be reviewed, edited and saved for later execution.

## Key Features

* Browser interaction recording using Playwright Codegen
* Automatic generation of Playwright test steps
* Pytest-compatible test function generation
* Structured test-case naming using SRS ID, TC ID, test type and description
* UI, Backend and Database test-type classification
* Duplicate test-case detection
* Input validation for test-case metadata
* Integrated Python code editor
* Syntax highlighting
* Find and search functionality
* Line numbers and code navigation
* Test-case counter
* Recent generated test files
* Screenshot capture on test failure
* Playwright trace capture
* Playwright storage-state support for authenticated sessions
* Persistent application configuration
* Built-in application scenario tests

## Technology Stack

* Python
* Tkinter
* Playwright
* Pytest
* Regular Expressions
* JSON
* Git / GitHub

## How It Works

AutoCraft follows a simple four-step workflow:

### 1. Enter Target URL

Provide the web application's URL that needs to be automated.

### 2. Define Test Identity

Enter:

* SRS ID
* Test Case ID
* Test Type
* Test Description

AutoCraft validates the fields and generates a consistent Python test-function name.

Example:

```text
test_SRS001_TC001_UI_Login
```

### 3. Record Browser Actions

AutoCraft launches Playwright Codegen and allows the user to interact with the target application.

Recorded browser actions are captured and presented inside the built-in code editor for review.

### 4. Save the Test Case

After reviewing the generated steps, the test case can be saved into the generated Playwright test file.

## Playwright Options

AutoCraft supports optional Playwright features including:

### Screenshot on Failure

Automatically captures a screenshot when a test fails.

### Trace Capture

Captures Playwright traces that can be inspected for debugging.

### Storage State

Allows an existing Playwright storage-state JSON file to be loaded so authenticated browser sessions can be reused.

## Generated Test Structure

Generated tests follow a pytest-compatible structure.

Example:

```python
def test_SRS001_TC001_UI_Login(page):
    page.goto("https://example.com")
    page.click("#login")
    expect(page).to_have_url("https://example.com/login")
```

## Installation

### Prerequisites

* Windows
* Python 3.10+
* pip

### Install the project

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/autocraft-playwright.git
cd autocraft-playwright
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install the Playwright browser:

```bash
playwright install chromium
```

## Running AutoCraft

Start the application:

```bash
python autocraft.py
```

## Running Built-in Tests

AutoCraft includes scenario tests for its core helper functions and configuration logic.

Run:

```bash
python autocraft.py --test
```

A successful execution reports the number of passed checks.

## Project Structure

```text
autocraft-playwright/
│
├── autocraft.py
├── README.md
├── requirements.txt
├── .gitignore
├── LICENSE
│
├── tests/
│   └── test_autocraft.py
│
├── docs/
│   └── screenshots/
│
└── .github/
    └── workflows/
        └── tests.yml
```

## Design Highlights

AutoCraft separates core test-generation logic from the desktop UI where practical, making key helper functions independently testable.

The application includes validation and duplicate-detection mechanisms to reduce invalid or duplicated generated test cases.

The built-in editor provides a review step between browser recording and test-case persistence, allowing generated actions to be inspected before they are saved.

## Current Scope

AutoCraft is currently focused on Windows-based web automation workflows using Playwright and pytest.

## Future Improvements

Potential future enhancements include:

* Page Object Model generation
* API test generation
* Additional browser support
* Configurable project/output directories
* Test-suite management
* HTML test-report integration
* CI/CD integration
* Test-case import/export
* Framework templates
* More advanced generated-code formatting

## Author

**Prajith S**

QA / Automation Test Engineer

## Disclaimer

This project is intended for testing applications that you are authorized to test. Do not use browser automation against systems without appropriate permission.

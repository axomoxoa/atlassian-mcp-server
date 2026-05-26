# Project Instructions

## Table of Contents

1. [Documentation First](#documentation-first)
2. [Testing](#testing)
3. [Documentation Sync](#documentation-sync)
4. [Markdown Structure](#markdown-structure)
5. [Documentation](#documentation)
6. [Change Discipline](#change-discipline)

## Best Practices

- Try to look out for best practices in code, documentation, testing, and project structure.
- If you see an opportunity to improve the project in any of these areas, take it!

## Security

- Peform security reviews for any code changes, especially those that handle authentication, secrets, or external communication.
- Follow secure coding practices and avoid hardcoding secrets or sensitive information in the codebase.
- Use environment variables or secure vaults for managing secrets and credentials.
- Scan code by using tools like `semgrep, codeql, bandit` to identify potential security issues before merging changes.
- Verify code based on OWASP top 10 security risks and ensure that the code does not introduce vulnerabilities such as injection, broken authentication, or sensitive data exposure.

## Testing

- Test first development approach must be followed for all code changes.
- Automated tests are required for any capability added or changed in this project.
- New functionality should include test coverage appropriate to the scope of the change.
- Regressions should be covered by automated tests when fixed.

## Documentation Sync

- Documentation in `documentation/` must be kept in sync with code and implementation.
- Any code or capability change that affects behavior, interfaces, or workflows must update the relevant documentation.

## Markdown Structure

- Any documentation markdown file must have a table of contents.
- The table of contents must be kept up to date with the document content.

## MCP

- Use always a dialog to ask for user input on tools, never ask for user input in free text without using a tool dialog. If a default value exists pre-fill the value in the dialog and allow the user to edit it before submission.
- On input dialog every invocation of tool should asks for all require paramaters. No previous value should be used to pre-fill the dialog, even if the same tool was used before. This is to ensure that user review all parameters on every tool invocation and avoid mistakes by reusing previous values without review.

## Documentation

## General

- Any documentation must have a table of contents.
- The table of contents must be kept up to date with the document content.
- Documentation should be clear, concise, and well-structured to facilitate understanding and navigation.
- Use consistent formatting and style across all documentation files.
- Use examples and diagrams where appropriate to illustrate concepts and workflows. (preferably using mermaid)
- Link to related documentation and resources to provide additional context and information.
- Avoid describing the same information redundantly across multiple documents; instead, link to a single source of truth when possible.
- For any code-related documentation, ensure that it is accurate and reflects the current state of the codebase.

### README.md

- File: /README.md
- Should provide a high-level overview of the project, including:
  - What the project is
  - Key features and capabilities
  - Quick start instructions
  - Links to detailed documentation

- Each major capability or tool should be briefly described in the README with links to the full documentation in `documentation/`.
- The README should be concise and focused on providing an introduction and navigation to the project.
- If possible show the core architecture of the component in graphical way by using mermaid diagrams.

### Implementation

- File: /documentation/implementation.md
- Should provide a detailed description of the implementation of the project, including:
  - Architecture overview (components, interactions, data flow)
  - Key components and their interactions
  - Data flow and processing
  - Any important design decisions or trade-offs made during development

### Installation

- File: /documentation/installatiion.md
- Should contain everything needed to get the project up and running, including:
  - Prerequisites
  - Setup steps
  - Claude Desktop configuration
  - MCP Inspector usage

### Dependencies

- File: /documentation/dependencies.md
- Should list all major dependencies and their purpose in the project.

### Tests

- File: tests.md
- Should list all tests in the project with:
  - What they test
  - Setup required
  - Assertions made

### Environment Variables

- File: /documentation/environment-variables.md
- Should contain all details for environment variables
- Each Environment Variable should be described by:
  - Name
  - Description
  - Possible values
  - Default value

### MCP Tool Documentation

- File Name: tools.md
- Tool documentation must contain a list of tools broken down by area.
- Tool documentation must use each tool as its own chapter or section.
- Each tool section must show:
  - description
  - input
    - schema: parameters with description, type, and whether required
    - example input
  - output
    - schema: parameters with description, type, and whether required
    - example input

## Change Discipline

- Any changes on documentation must remain consistent with these instructions.
- Any changes on code base (test, config, tests,..) must be synchronized with documentation.

## Jira Template Ticket Creation Workflow

- Tool selection is mandatory:
  - If the user asks to create a ticket "from template" or provides `template_issue_key` (for example `FLICA-122`), use `jira_create_ticket_from_template`.
  - Do not use `jira_create_issue` for template-based requests.

- For `jira_create_ticket_from_template`, if the tool returns `status=needs_placeholder_values`, always collect user input for each placeholder before retrying creation.
- Prompt the user once per placeholder, using the placeholder name in the question text (for example: `Provide a value for {integration}`).
- Do not skip placeholders and do not batch multiple placeholders into one free-text prompt.
- After collecting values for all required placeholders, call `jira_create_ticket_from_template` again with `placeholder_values` filled for every required placeholder.
- If the user leaves a required placeholder empty, ask again for that specific placeholder.

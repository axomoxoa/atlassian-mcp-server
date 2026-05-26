# MCP Tools

## Table of Contents

1. [Overview](#overview)
2. [Recommended Workflows](#recommended-workflows)
3. [Core Tools](#core-tools)
4. [Jira Metadata and Discovery](#jira-metadata-and-discovery)
5. [Jira Query and Validation](#jira-query-and-validation)
6. [Jira Issue Lifecycle](#jira-issue-lifecycle)
7. [Jira Comments and Worklogs](#jira-comments-and-worklogs)
8. [Jira Project Structure and Links](#jira-project-structure-and-links)
9. [Jira Agile](#jira-agile)
10. [Jira Service Management](#jira-service-management)
11. [Jira Watchers](#jira-watchers)
12. [Jira Forms](#jira-forms)
13. [Jira Development Info](#jira-development-info)
14. [Jira Attachments and Images](#jira-attachments-and-images)
15. [Confluence Pages and Search](#confluence-pages-and-search)
16. [Confluence Comments and Labels](#confluence-comments-and-labels)
17. [Confluence Attachments and Images](#confluence-attachments-and-images)
18. [Resource](#resource)

## Overview

This server exposes 71 MCP tools and one MCP resource.

- 2 core tools
- 51 Jira tools
- 18 Confluence tools
- 1 MCP resource: `atlassian://config`

The source of truth is `TOOLSET_BY_NAME` in `src/atlassian_mcp_server/server.py`.

Visibility is controlled by the configured toolsets:

- `core`
- `jira-read`
- `jira-write`
- `confluence-read`
- `confluence-write`

The examples below are illustrative and use short sample values. Output examples focus on the top-level shape returned by the current implementation.

## Recommended Workflows

### Jira Query Workflow

1. Build JQL with `jira_build_jql`.
2. Validate it with `jira_validate_jql`.
3. Execute it with `jira_search_issues`.

### Jira Issue Update Workflow

1. Load the issue with `jira_get_issue`.
2. Inspect valid transitions with `jira_get_transitions`.
3. Add context with `jira_add_comment` or `jira_add_worklog`.
4. Move the issue with `jira_transition_issue`.

### Confluence Content Workflow

1. Find content with `confluence_search`.
2. Read it with `confluence_get_page`.
3. Change it with `confluence_update_page`.
4. Add files with `confluence_upload_attachment`.
5. Annotate it with `confluence_add_comment` or `confluence_add_label`.

## Core Tools

### atlassian_check_connection

Description:
Verify Jira and Confluence connectivity with the current configuration.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field      | Type   | Required | Description                                |
| ---------- | ------ | -------- | ------------------------------------------ |
| status     | string | Yes      | Overall status across Jira and Confluence. |
| jira       | object | Yes      | Jira connectivity status block.            |
| confluence | object | Yes      | Confluence connectivity status block.      |

Example output:

```yaml
status: ok
jira:
  status: ok
  display_name: Jane Doe
confluence:
  status: ok
  result_count: 1
```

### atlassian_get_myself

Description:
Return the authenticated Atlassian account profile.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field         | Type    | Required | Description                            |
| ------------- | ------- | -------- | -------------------------------------- |
| account_id    | string  | No       | Atlassian account id.                  |
| display_name  | string  | No       | Human-readable display name.           |
| email_address | string  | No       | Email address when exposed by the API. |
| active        | boolean | No       | Whether the account is active.         |
| time_zone     | string  | No       | Preferred time zone.                   |

Example output:

```yaml
account_id: abc123
display_name: Jane Doe
email_address: jane@example.com
active: true
time_zone: Europe/Berlin
```

## Jira Metadata and Discovery

### jira_list_projects

Description:
List Jira projects visible to the configured account.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field  | Type          | Required | Description                   |
| ------ | ------------- | -------- | ----------------------------- |
| result | array<object> | Yes      | Compact Jira project objects. |

Example output:

```yaml
- id: 10000
  key: ENG
  name: Engineering
```

### jira_list_fields

Description:
List Jira fields available to the current account.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field  | Type          | Required | Description                 |
| ------ | ------------- | -------- | --------------------------- |
| result | array<object> | Yes      | Compact Jira field objects. |

Example output:

```yaml
- id: summary
  name: Summary
  custom: false
```

### jira_search_fields

Description:
Search Jira fields by field id or display name.

Input schema:

| Parameter | Type    | Required | Description                                      |
| --------- | ------- | -------- | ------------------------------------------------ |
| query     | string  | Yes      | Text to match against field id or name.          |
| limit     | integer | No       | Maximum number of fields to return. Default: 20. |

Example input:

```yaml
query: story
limit: 5
```

Output schema:

| Field  | Type          | Required | Description                     |
| ------ | ------------- | -------- | ------------------------------- |
| result | array<object> | Yes      | Matching compact field objects. |

Example output:

```yaml
- id: customfield_10016
  name: Story Points
  custom: true
```

### jira_get_field_options

Description:
Get allowed values for a Jira field. On Cloud this uses field context APIs. On Server or Data Center it can resolve from create metadata.

Input schema:

| Parameter   | Type   | Required | Description                                       |
| ----------- | ------ | -------- | ------------------------------------------------- |
| field_id    | string | Yes      | Jira field id.                                    |
| context_id  | string | No       | Field context id, mainly for Cloud.               |
| project_key | string | No       | Project key for Server or Data Center resolution. |
| issue_type  | string | No       | Issue type for Server or Data Center resolution.  |

Example input:

```yaml
field_id: customfield_10016
context_id: 10100
```

Output schema:

| Field   | Type          | Required | Description                           |
| ------- | ------------- | -------- | ------------------------------------- |
| values  | array<object> | No       | Resolved allowed values when present. |
| context | object        | No       | Field-context metadata when present.  |

Example output:

```yaml
values:
  - id: 1
    value: Small
  - id: 2
    value: Medium
```

### jira_list_statuses

Description:
List Jira statuses visible to the current account.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field  | Type          | Required | Description                  |
| ------ | ------------- | -------- | ---------------------------- |
| result | array<object> | Yes      | Compact Jira status objects. |

Example output:

```yaml
- id: 3
  name: In Progress
  status_category: in-flight
```

### jira_list_issue_types

Description:
List Jira issue types visible to the current account.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field  | Type          | Required | Description                      |
| ------ | ------------- | -------- | -------------------------------- |
| result | array<object> | Yes      | Compact Jira issue-type objects. |

Example output:

```yaml
- id: 10001
  name: Story
  subtask: false
```

### jira_get_user_profile

Description:
Get a Jira user profile by account id on Cloud or by username on Server or Data Center.

Input schema:

| Parameter       | Type   | Required | Description                                     |
| --------------- | ------ | -------- | ----------------------------------------------- |
| user_identifier | string | Yes      | Account id or username depending on deployment. |

Example input:

```yaml
user_identifier: 5b10ac8d82e05b22cc7d4ef5
```

Output schema:

| Field       | Type    | Required | Description                    |
| ----------- | ------- | -------- | ------------------------------ |
| accountId   | string  | No       | Atlassian account id on Cloud. |
| displayName | string  | No       | Human-readable name.           |
| active      | boolean | No       | Whether the user is active.    |

Example output:

```yaml
accountId: 5b10ac8d82e05b22cc7d4ef5
displayName: Jane Doe
active: true
```

## Jira Query and Validation

### jira_build_jql

Description:
Build a JQL query from structured filters.

Input schema:

| Parameter       | Type          | Required | Description                                        |
| --------------- | ------------- | -------- | -------------------------------------------------- |
| project_keys    | array<string> | No       | Project keys to include.                           |
| assignee        | string        | No       | Assignee name or `currentUser()`.                  |
| reporter        | string        | No       | Reporter name.                                     |
| statuses        | array<string> | No       | Status names to include.                           |
| issue_types     | array<string> | No       | Issue types to include.                            |
| priorities      | array<string> | No       | Priorities to include.                             |
| text            | string        | No       | Text search against summary and description.       |
| updated_since   | string        | No       | Relative or absolute lower bound for `updated >=`. |
| resolution      | string        | No       | Resolution filter.                                 |
| order_by        | string        | No       | Sort field. Default: updated.                      |
| order_direction | string        | No       | Sort direction. Default: DESC.                     |

Example input:

```yaml
project_keys:
  - ENG
statuses:
  - In Progress
assignee: currentUser()
order_by: updated
order_direction: DESC
```

Output schema:

| Field | Type   | Required | Description               |
| ----- | ------ | -------- | ------------------------- |
| jql   | string | Yes      | Generated JQL expression. |

Example output:

```yaml
jql: project = ENG AND assignee = currentUser() AND status in ("In Progress") ORDER BY updated DESC
```

### jira_search_issues

Description:
Search Jira issues using JQL with pagination support.

Input schema:

| Parameter      | Type          | Required | Description                                      |
| -------------- | ------------- | -------- | ------------------------------------------------ |
| jql            | string        | Yes      | JQL query to execute.                            |
| limit          | integer       | No       | Maximum results to return. Default: 10.          |
| fields         | array<string> | No       | Requested issue fields.                          |
| start_at       | integer       | No       | Pagination offset. Default: 0.                   |
| validate_query | boolean       | No       | Whether Jira validates the query. Default: true. |

Example input:

```yaml
jql: project = ENG ORDER BY updated DESC
limit: 2
fields:
  - summary
  - status
start_at: 0
validate_query: true
```

Output schema:

| Field       | Type          | Required | Description                      |
| ----------- | ------------- | -------- | -------------------------------- |
| issues      | array<object> | Yes      | Matching Jira issues.            |
| total       | integer       | Yes      | Total number of matching issues. |
| start_at    | integer       | Yes      | Current offset.                  |
| max_results | integer       | Yes      | Returned page size.              |

Example output:

```yaml
issues:
  - key: ENG-123
    fields:
      summary: Investigate incident
total: 14
start_at: 0
max_results: 2
```

### jira_validate_jql

Description:
Validate JQL syntax and access without returning a full result set.

Input schema:

| Parameter | Type   | Required | Description            |
| --------- | ------ | -------- | ---------------------- |
| jql       | string | Yes      | JQL query to validate. |

Example input:

```yaml
jql: project = ENG ORDER BY updated DESC
```

Output schema:

| Field  | Type    | Required | Description                                      |
| ------ | ------- | -------- | ------------------------------------------------ |
| valid  | boolean | Yes      | Whether the query is valid.                      |
| jql    | string  | No       | Echoed JQL when validation runs.                 |
| total  | integer | No       | Small validation search result count on success. |
| reason | string  | No       | Failure reason when invalid.                     |
| hint   | string  | No       | Guidance when the input does not look like JQL.  |

Example output:

```yaml
valid: true
jql: project = ENG ORDER BY updated DESC
total: 14
```

### jira_query_issues_from_text

Description:
Build and run a JQL query from structured parameters derived from a natural-language request.

Input schema:

| Parameter     | Type          | Required | Description                             |
| ------------- | ------------- | -------- | --------------------------------------- |
| project_keys  | array<string> | No       | Project keys to include.                |
| assignee      | string        | No       | Assignee name or `currentUser()`.       |
| reporter      | string        | No       | Reporter name.                          |
| statuses      | array<string> | No       | Status names to include.                |
| issue_types   | array<string> | No       | Issue types to include.                 |
| updated_since | string        | No       | Relative or absolute updated filter.    |
| text          | string        | No       | Keyword search text.                    |
| limit         | integer       | No       | Maximum results to return. Default: 10. |
| start_at      | integer       | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
project_keys:
  - ENG
assignee: currentUser()
updated_since: -7d
limit: 5
```

Output schema:

| Field       | Type          | Required | Description           |
| ----------- | ------------- | -------- | --------------------- |
| issues      | array<object> | Yes      | Matching Jira issues. |
| total       | integer       | Yes      | Total matches.        |
| start_at    | integer       | Yes      | Current offset.       |
| max_results | integer       | Yes      | Returned page size.   |
| jql_used    | string        | Yes      | Generated JQL string. |

Example output:

```yaml
issues:
  - key: ENG-101
total: 5
start_at: 0
max_results: 5
jql_used: project = ENG AND assignee = currentUser() AND updated >= -7d ORDER BY updated DESC
```

## Jira Issue Lifecycle

### jira_get_issue

Description:
Fetch a Jira issue by key.

Input schema:

| Parameter | Type   | Required | Description                  |
| --------- | ------ | -------- | ---------------------------- |
| issue_key | string | Yes      | Issue key such as `ENG-123`. |

Example input:

```yaml
issue_key: ENG-123
```

Output schema:

| Field  | Type   | Required | Description               |
| ------ | ------ | -------- | ------------------------- |
| id     | string | No       | Jira issue id.            |
| key    | string | No       | Jira issue key.           |
| fields | object | No       | Full Jira fields payload. |

Example output:

```yaml
id: 10001
key: ENG-123
fields:
  summary: Investigate incident
```

### jira_create_issue

Description:
Create a Jira issue with optional description, assignee, and additional JSON fields.

Input schema:

| Parameter         | Type   | Required | Description                      |
| ----------------- | ------ | -------- | -------------------------------- |
| project_key       | string | Yes      | Target Jira project key.         |
| summary           | string | Yes      | Issue summary.                   |
| issue_type        | string | Yes      | Issue type name.                 |
| description       | string | No       | Issue description.               |
| assignee          | string | No       | Assignee identifier.             |
| additional_fields | string | No       | JSON object encoded as a string. |

Example input:

```yaml
project_key: ENG
summary: Investigate alert noise
issue_type: Task
description: Review current alerting thresholds.
```

Routing note:

- Use `jira_create_ticket_from_template` instead of `jira_create_issue` when creating from a template issue key or when text contains placeholders like `{integration}`.
- `jira_create_issue` will reject unresolved template placeholders in summary/description.

Output schema:

| Field  | Type   | Required | Description                  |
| ------ | ------ | -------- | ---------------------------- |
| status | string | Yes      | Creation status.             |
| issue  | object | Yes      | Compact created issue block. |

Example output:

```yaml
status: created
issue:
  id: 10012
  key: ENG-456
  url: https://jira.digital.ingka.com/browse/ENG-456
```

### jira_list_templates

Description:
List all template issues in a Jira project. Templates are detected from issue labels using `marker_value` (default: `template`).

Input schema:

| Parameter    | Type   | Required | Description                                                   |
| ------------ | ------ | -------- | ------------------------------------------------------------- |
| project_key  | string | Yes      | Jira project key to scan.                                     |
| marker_value | string | No       | Marker value used to identify templates. Default: `template`. |

Example input:

```yaml
project_key: FLICA
marker_value: template
```

Output schema:

| Field          | Type          | Required | Description                                         |
| -------------- | ------------- | -------- | --------------------------------------------------- |
| project_key    | string        | Yes      | Jira project key that was scanned.                  |
| marker_value   | string        | Yes      | Marker used for matching.                           |
| template_count | integer       | Yes      | Number of matching templates.                       |
| scanned_issues | integer       | Yes      | Number of issues scanned in the project.            |
| total_issues   | integer       | Yes      | Total issue count reported by Jira for the project. |
| templates      | array<object> | Yes      | Matching template issue summaries.                  |

Example output:

```yaml
project_key: FLICA
marker_value: template
template_count: 2
scanned_issues: 18
total_issues: 18
templates:
  - key: FLICA-12
    summary: Create onboarding ticket for {system_name}
    issue_type: Story
    status: To Do
    template_markers:
      - labels
```

### jira_create_ticket_from_template

Description:
Create a Jira issue from a template issue. Placeholders in summary, description, acceptance criteria, or definition-of-done fields use the form `{placeholder}`. If values are missing, the tool returns the missing placeholders and one question per placeholder so the caller can ask the user one-by-one (by placeholder name) and call the tool again.

Routing note:

- If the user request mentions a template issue key (for example `FLICA-122`) or says "from template", always use this tool.

Input schema:

| Parameter          | Type    | Required | Description                                                                                                                                                                     |
| ------------------ | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| template_issue_key | string  | Yes      | Jira issue key for the template ticket.                                                                                                                                         |
| project_key        | string  | No       | Target project key. Defaults to the template issue project.                                                                                                                     |
| placeholder_values | string  | No       | JSON object string mapping placeholder names to replacement values. For LLM output, use valid JSON escaping (`\"` for embedded quotes; escape backslashes/slashes when needed). |
| include_subtasks   | boolean | No       | Clone subtasks from the template. Default: True.                                                                                                                                |

Example input:

```yaml
template_issue_key: FLICA-12
include_subtasks: true
project_key: FLICA
placeholder_values: '{"system_name":"Payments API","owner":"Jane Doe","note":"Use \\\"Blue\\\" lane","path":"https:\\/\\/example.com\\/runbook"}'
```

Encoding note for LLM-generated JSON strings:

- Embedded double quotes inside values must be escaped as `\"`.
- Backslashes must be escaped as `\\`.
- Slashes can be escaped as `\/` when needed.

Output schema:

| Field              | Type          | Required | Description                                                  |
| ------------------ | ------------- | -------- | ------------------------------------------------------------ |
| status             | string        | Yes      | `needs_placeholder_values` or `created`.                     |
| template_issue_key | string        | Yes      | Source template issue key.                                   |
| project_key        | string        | Yes      | Target project key.                                          |
| include_subtasks   | boolean       | Yes      | Whether subtasks were created.                               |
| placeholders       | array<string> | No       | Missing placeholder names when user input is still required. |
| questions          | array<object> | No       | Prompt hints for collecting missing placeholder values.      |
| preview            | object        | No       | Summary and issue-type preview before creation.              |
| issue              | object        | No       | Created issue metadata when successful.                      |
| subtasks           | array<object> | No       | Created subtask metadata when successful.                    |
| placeholders_used  | object        | No       | Placeholder replacements used during creation.               |

Example output:

```yaml
status: needs_placeholder_values
template_issue_key: FLICA-12
project_key: FLICA
placeholders:
  - system_name
questions:
  - placeholder: system_name
    prompt: Provide a value for {system_name}
preview:
  summary: Create onboarding ticket for {system_name}
  issue_type: Story
```

Caller behavior requirement:

- Prompt the user once per placeholder listed in `placeholders`.
- Use the placeholder name in each prompt.
- Collect one input per prompt and retry the tool with all required values.

Example output (when all placeholders are provided):
include_subtasks: true

```yaml
status: created
template_issue_key: FLICA-12
project_key: FLICA
issue:
  id: 10456
  key: FLICA-125
  url: https://jira.digital.ingka.com/browse/FLICA-125
subtasks:
  - source_issue_key: FLICA-13
    issue:
      id: 10457
      key: FLICA-126
      url: https://jira.digital.ingka.com/browse/FLICA-126
placeholders_used:
  system_name: Payments API
  owner: Jane Doe
```

### jira_clone_ticket

Description:
Clone a Jira issue, optionally including subtasks and attachments. Before execution, confirm the clone scope with the user for `include_subtasks` and `include_attachments`. Defaults are `true` for both, so the user can simply confirm to proceed. The cloned issue is explicitly unassigned, copies acceptance criteria and definition-of-done fields, and does not copy comments.

Input schema:

| Parameter           | Type    | Required | Description                                                                     |
| ------------------- | ------- | -------- | ------------------------------------------------------------------------------- |
| source_issue_key    | string  | Yes      | Jira issue key to clone.                                                        |
| project_key         | string  | No       | Target project key. Defaults to the source issue project.                       |
| include_subtasks    | boolean | No       | Clone subtasks under the new parent issue. Default: `true`.                     |
| include_attachments | boolean | No       | Copy Jira attachments to the cloned issue and cloned subtasks. Default: `true`. |

Example input:

```yaml
source_issue_key: FLICA-101
include_subtasks: true
include_attachments: true
```

Output schema:

| Field               | Type          | Required | Description                                    |
| ------------------- | ------------- | -------- | ---------------------------------------------- |
| status              | string        | Yes      | Clone status.                                  |
| source_issue_key    | string        | Yes      | Source issue key.                              |
| project_key         | string        | Yes      | Target project key.                            |
| include_subtasks    | boolean       | Yes      | Whether subtasks were cloned.                  |
| include_attachments | boolean       | Yes      | Whether attachments were copied.               |
| issue               | object        | Yes      | Created parent issue metadata.                 |
| subtasks            | array<object> | Yes      | Created cloned subtask metadata.               |
| attachments_copied  | integer       | Yes      | Number of attachments copied to cloned issues. |

Example output:

```yaml
status: created
source_issue_key: FLICA-101
project_key: FLICA
include_subtasks: true
include_attachments: true
issue:
  id: 10204
  key: FLICA-204
  url: https://jira.digital.ingka.com/browse/FLICA-204
subtasks:
  - source_issue_key: FLICA-102
    issue:
      id: 10205
      key: FLICA-205
      url: https://jira.digital.ingka.com/browse/FLICA-205
attachments_copied: 3
```

### jira_update_issue

Description:
Update an existing Jira issue using a JSON object encoded as a string.

Input schema:

| Parameter | Type   | Required | Description                                       |
| --------- | ------ | -------- | ------------------------------------------------- |
| issue_key | string | Yes      | Target issue key.                                 |
| fields    | string | Yes      | JSON object of field updates encoded as a string. |

Example input:

```yaml
issue_key: ENG-456
fields: '{"summary":"Updated summary"}'
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Update status when returned by the API. |
| result | object | No       | Provider-specific update payload.       |

Example output:

```yaml
status: updated
```

### jira_delete_issue

Description:
Delete a Jira issue by key.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: ENG-456
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Delete status when returned by the API. |

Example output:

```yaml
status: deleted
```

### jira_get_transitions

Description:
List transitions currently available for a Jira issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: ENG-123
```

Output schema:

| Field  | Type          | Required | Description                                                  |
| ------ | ------------- | -------- | ------------------------------------------------------------ |
| result | array<object> | Yes      | Available transitions with ids and destination status names. |

Example output:

```yaml
- id: 31
  name: Done
  to_status: Done
```

### jira_transition_issue

Description:
Transition a Jira issue by transition name or transition id.

Input schema:

| Parameter       | Type   | Required | Description               |
| --------------- | ------ | -------- | ------------------------- |
| issue_key       | string | Yes      | Target issue key.         |
| transition_name | string | No       | Transition name to apply. |
| transition_id   | string | No       | Transition id to apply.   |

Example input:

```yaml
issue_key: ENG-123
transition_name: Done
```

Output schema:

| Field     | Type   | Required | Description                                    |
| --------- | ------ | -------- | ---------------------------------------------- |
| status    | string | No       | Transition result status.                      |
| issue_key | string | No       | Issue key echoed by the implementation or API. |

Example output:

```yaml
status: transitioned
issue_key: ENG-123
```

## Jira Comments and Worklogs

### jira_add_comment

Description:
Add a plain-text comment to a Jira issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |
| comment   | string | Yes      | Comment body.     |

Example input:

```yaml
issue_key: ENG-123
comment: Investigating root cause now.
```

Output schema:

| Field      | Type   | Required | Description                         |
| ---------- | ------ | -------- | ----------------------------------- |
| issue_key  | string | Yes      | Target issue key.                   |
| comment_id | string | No       | Created comment id.                 |
| author     | string | No       | Display name of the comment author. |
| status     | string | Yes      | Creation status.                    |

Example output:

```yaml
issue_key: ENG-123
comment_id: 10000
author: Jane Doe
status: created
```

### jira_edit_comment

Description:
Edit an existing Jira comment.

Input schema:

| Parameter  | Type   | Required | Description               |
| ---------- | ------ | -------- | ------------------------- |
| issue_key  | string | Yes      | Target issue key.         |
| comment_id | string | Yes      | Comment id.               |
| comment    | string | Yes      | Replacement comment body. |

Example input:

```yaml
issue_key: ENG-123
comment_id: 10000
comment: Root cause confirmed and fix is in progress.
```

Output schema:

| Field      | Type   | Required | Description                         |
| ---------- | ------ | -------- | ----------------------------------- |
| issue_key  | string | Yes      | Target issue key.                   |
| comment_id | string | Yes      | Updated comment id.                 |
| author     | string | No       | Display name of the comment author. |
| status     | string | Yes      | Update status.                      |

Example output:

```yaml
issue_key: ENG-123
comment_id: 10000
author: Jane Doe
status: updated
```

### jira_get_worklog

Description:
Get worklog entries for a Jira issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: ENG-123
```

Output schema:

| Field     | Type          | Required | Description                  |
| --------- | ------------- | -------- | ---------------------------- |
| issue_key | string        | Yes      | Target issue key.            |
| count     | integer       | Yes      | Number of worklogs returned. |
| worklogs  | array<object> | Yes      | Worklog entries.             |

Example output:

```yaml
issue_key: ENG-123
count: 1
worklogs:
  - id: 20001
    timeSpent: 1h
```

### jira_add_worklog

Description:
Add a worklog entry to a Jira issue.

Input schema:

| Parameter  | Type   | Required | Description                                   |
| ---------- | ------ | -------- | --------------------------------------------- |
| issue_key  | string | Yes      | Target issue key.                             |
| time_spent | string | Yes      | Jira time-spent string such as `1h` or `30m`. |
| comment    | string | No       | Optional worklog comment.                     |
| started    | string | No       | Optional start timestamp.                     |

Example input:

```yaml
issue_key: ENG-123
time_spent: 45m
comment: Reviewed logs and metrics.
```

Output schema:

| Field      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| issue_key  | string | Yes      | Target issue key.   |
| worklog_id | string | No       | Created worklog id. |
| status     | string | Yes      | Creation status.    |

Example output:

```yaml
issue_key: ENG-123
worklog_id: 20002
status: created
```

## Jira Project Structure and Links

### jira_get_project_versions

Description:
Get fix versions for a Jira project.

Input schema:

| Parameter   | Type   | Required | Description         |
| ----------- | ------ | -------- | ------------------- |
| project_key | string | Yes      | Target project key. |

Example input:

```yaml
project_key: ENG
```

Output schema:

| Field  | Type          | Required | Description              |
| ------ | ------------- | -------- | ------------------------ |
| result | array<object> | Yes      | Project version objects. |

Example output:

```yaml
- id: 10020
  name: 2026.04
  released: false
```

### jira_get_project_components

Description:
Get components for a Jira project.

Input schema:

| Parameter   | Type   | Required | Description         |
| ----------- | ------ | -------- | ------------------- |
| project_key | string | Yes      | Target project key. |

Example input:

```yaml
project_key: ENG
```

Output schema:

| Field  | Type          | Required | Description                |
| ------ | ------------- | -------- | -------------------------- |
| result | array<object> | Yes      | Project component objects. |

Example output:

```yaml
- id: 30001
  name: API
```

### jira_get_link_types

Description:
List available Jira issue link types.

Input schema:

| Parameter | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| none      | none | Yes      | This tool does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field  | Type          | Required | Description                 |
| ------ | ------------- | -------- | --------------------------- |
| result | array<object> | Yes      | Available issue-link types. |

Example output:

```yaml
- id: 10000
  name: Relates
  inward: relates to
  outward: relates to
```

### jira_create_issue_link

Description:
Create a link between two Jira issues.

Input schema:

| Parameter         | Type   | Required | Description            |
| ----------------- | ------ | -------- | ---------------------- |
| link_type         | string | Yes      | Jira link type name.   |
| inward_issue_key  | string | Yes      | Inward issue key.      |
| outward_issue_key | string | Yes      | Outward issue key.     |
| comment           | string | No       | Optional link comment. |

Example input:

```yaml
link_type: Relates
inward_issue_key: ENG-100
outward_issue_key: ENG-123
```

Output schema:

| Field  | Type   | Required | Description                                    |
| ------ | ------ | -------- | ---------------------------------------------- |
| status | string | No       | Link-creation status when returned by the API. |

Example output:

```yaml
status: created
```

### jira_remove_issue_link

Description:
Remove a Jira issue link by id.

Input schema:

| Parameter | Type   | Required | Description        |
| --------- | ------ | -------- | ------------------ |
| link_id   | string | Yes      | Link id to remove. |

Example input:

```yaml
link_id: 50001
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Delete status when returned by the API. |

Example output:

```yaml
status: deleted
```

## Jira Agile

### jira_get_agile_boards

Description:
List Jira Agile boards with optional filtering.

Input schema:

| Parameter         | Type    | Required | Description                             |
| ----------------- | ------- | -------- | --------------------------------------- |
| limit             | integer | No       | Maximum results to return. Default: 25. |
| start_at          | integer | No       | Pagination offset. Default: 0.          |
| board_type        | string  | No       | Optional board type filter.             |
| project_key_or_id | string  | No       | Optional project filter.                |
| name              | string  | No       | Optional board name filter.             |

Example input:

```yaml
limit: 10
board_type: scrum
project_key_or_id: ENG
```

Output schema:

| Field      | Type          | Required | Description                             |
| ---------- | ------------- | -------- | --------------------------------------- |
| values     | array<object> | No       | Matching board records.                 |
| startAt    | integer       | No       | Pagination offset from Jira Agile APIs. |
| maxResults | integer       | No       | Page size from Jira Agile APIs.         |

Example output:

```yaml
values:
  - id: 7
    name: ENG Scrum
startAt: 0
maxResults: 10
```

### jira_get_board_issues

Description:
Get issues on an Agile board.

Input schema:

| Parameter | Type    | Required | Description                             |
| --------- | ------- | -------- | --------------------------------------- |
| board_id  | string  | Yes      | Agile board id.                         |
| jql       | string  | No       | Additional JQL filter.                  |
| limit     | integer | No       | Maximum results to return. Default: 25. |
| start_at  | integer | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
board_id: 7
limit: 5
```

Output schema:

| Field      | Type          | Required | Description          |
| ---------- | ------------- | -------- | -------------------- |
| issues     | array<object> | No       | Issues on the board. |
| startAt    | integer       | No       | Pagination offset.   |
| maxResults | integer       | No       | Page size.           |

Example output:

```yaml
issues:
  - key: ENG-123
startAt: 0
maxResults: 5
```

### jira_get_sprints_from_board

Description:
List sprints for an Agile board.

Input schema:

| Parameter | Type    | Required | Description                             |
| --------- | ------- | -------- | --------------------------------------- |
| board_id  | string  | Yes      | Agile board id.                         |
| state     | string  | No       | Optional sprint state filter.           |
| limit     | integer | No       | Maximum results to return. Default: 25. |
| start_at  | integer | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
board_id: 7
state: active
```

Output schema:

| Field      | Type          | Required | Description        |
| ---------- | ------------- | -------- | ------------------ |
| values     | array<object> | No       | Sprint records.    |
| startAt    | integer       | No       | Pagination offset. |
| maxResults | integer       | No       | Page size.         |

Example output:

```yaml
values:
  - id: 22
    name: Sprint 24
    state: active
startAt: 0
maxResults: 25
```

### jira_get_sprint_issues

Description:
Get issues in a sprint.

Input schema:

| Parameter | Type    | Required | Description                             |
| --------- | ------- | -------- | --------------------------------------- |
| sprint_id | string  | Yes      | Sprint id.                              |
| jql       | string  | No       | Additional JQL filter.                  |
| limit     | integer | No       | Maximum results to return. Default: 25. |
| start_at  | integer | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
sprint_id: 22
limit: 5
```

Output schema:

| Field      | Type          | Required | Description        |
| ---------- | ------------- | -------- | ------------------ |
| issues     | array<object> | No       | Sprint issues.     |
| startAt    | integer       | No       | Pagination offset. |
| maxResults | integer       | No       | Page size.         |

Example output:

```yaml
issues:
  - key: ENG-123
startAt: 0
maxResults: 5
```

### jira_create_sprint

Description:
Create a sprint on an Agile board.

Input schema:

| Parameter  | Type   | Required | Description                      |
| ---------- | ------ | -------- | -------------------------------- |
| name       | string | Yes      | Sprint name.                     |
| board_id   | string | Yes      | Agile board id.                  |
| start_date | string | No       | Optional sprint start timestamp. |
| end_date   | string | No       | Optional sprint end timestamp.   |
| goal       | string | No       | Optional sprint goal.            |

Example input:

```yaml
name: Sprint 25
board_id: 7
goal: Finish incident follow-up items
```

Output schema:

| Field | Type    | Required | Description        |
| ----- | ------- | -------- | ------------------ |
| id    | integer | No       | Created sprint id. |
| name  | string  | No       | Sprint name.       |
| state | string  | No       | Sprint state.      |

Example output:

```yaml
id: 25
name: Sprint 25
state: future
```

### jira_update_sprint

Description:
Update sprint metadata or sprint state.

Input schema:

| Parameter  | Type   | Required | Description              |
| ---------- | ------ | -------- | ------------------------ |
| sprint_id  | string | Yes      | Sprint id.               |
| name       | string | No       | Updated sprint name.     |
| state      | string | No       | Updated sprint state.    |
| start_date | string | No       | Updated start timestamp. |
| end_date   | string | No       | Updated end timestamp.   |
| goal       | string | No       | Updated sprint goal.     |

Example input:

```yaml
sprint_id: 25
state: active
```

Output schema:

| Field | Type    | Required | Description           |
| ----- | ------- | -------- | --------------------- |
| id    | integer | No       | Updated sprint id.    |
| name  | string  | No       | Updated sprint name.  |
| state | string  | No       | Updated sprint state. |

Example output:

```yaml
id: 25
name: Sprint 25
state: active
```

### jira_add_issues_to_sprint

Description:
Add multiple issues to a sprint.

Input schema:

| Parameter  | Type          | Required | Description                          |
| ---------- | ------------- | -------- | ------------------------------------ |
| sprint_id  | string        | Yes      | Sprint id.                           |
| issue_keys | array<string> | Yes      | Non-empty list of issue keys to add. |

Example input:

```yaml
sprint_id: 25
issue_keys:
  - ENG-123
  - ENG-124
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Update status when returned by the API. |

Example output:

```yaml
status: updated
```

## Jira Service Management

### jira_get_service_desk_for_project

Description:
Get service desk information for a project key.

Input schema:

| Parameter   | Type   | Required | Description       |
| ----------- | ------ | -------- | ----------------- |
| project_key | string | Yes      | Jira project key. |

Example input:

```yaml
project_key: HELP
```

Output schema:

| Field        | Type    | Required | Description                              |
| ------------ | ------- | -------- | ---------------------------------------- |
| project_key  | string  | Yes      | Requested project key.                   |
| found        | boolean | Yes      | Whether a linked service desk was found. |
| service_desk | object  | No       | Service desk details when found.         |

Example output:

```yaml
project_key: HELP
found: true
service_desk:
  id: 3
  projectKey: HELP
```

### jira_get_service_desk_queues

Description:
List queues for a Jira Service Management service desk.

Input schema:

| Parameter       | Type    | Required | Description                             |
| --------------- | ------- | -------- | --------------------------------------- |
| service_desk_id | string  | Yes      | Service desk id.                        |
| limit           | integer | No       | Maximum results to return. Default: 50. |
| start_at        | integer | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
service_desk_id: 3
limit: 10
```

Output schema:

| Field  | Type          | Required | Description        |
| ------ | ------------- | -------- | ------------------ |
| values | array<object> | No       | Queue records.     |
| start  | integer       | No       | Pagination offset. |
| limit  | integer       | No       | Page size.         |

Example output:

```yaml
values:
  - id: 11
    name: Triage
start: 0
limit: 10
```

### jira_get_queue_issues

Description:
Get issues in a Jira Service Management queue.

Input schema:

| Parameter       | Type    | Required | Description                             |
| --------------- | ------- | -------- | --------------------------------------- |
| service_desk_id | string  | Yes      | Service desk id.                        |
| queue_id        | string  | Yes      | Queue id.                               |
| limit           | integer | No       | Maximum results to return. Default: 25. |
| start_at        | integer | No       | Pagination offset. Default: 0.          |

Example input:

```yaml
service_desk_id: 3
queue_id: 11
limit: 5
```

Output schema:

| Field  | Type          | Required | Description        |
| ------ | ------------- | -------- | ------------------ |
| values | array<object> | No       | Queue issues.      |
| start  | integer       | No       | Pagination offset. |
| limit  | integer       | No       | Page size.         |

Example output:

```yaml
values:
  - issueKey: HELP-22
start: 0
limit: 5
```

### jira_get_issue_dates

Description:
Get common date fields for a Jira issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: HELP-22
```

Output schema:

| Field          | Type   | Required | Description                        |
| -------------- | ------ | -------- | ---------------------------------- |
| created        | string | No       | Created timestamp.                 |
| updated        | string | No       | Updated timestamp.                 |
| resolutiondate | string | No       | Resolution timestamp when present. |

Example output:

```yaml
created: "2026-04-20T08:00:00.000+0000"
updated: "2026-04-21T14:20:00.000+0000"
resolutiondate: null
```

### jira_get_issue_sla

Description:
Get Jira Service Management SLA information for an issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: HELP-22
```

Output schema:

| Field           | Type          | Required | Description           |
| --------------- | ------------- | -------- | --------------------- |
| completedCycles | array<object> | No       | Completed SLA cycles. |
| ongoingCycle    | object        | No       | Current SLA cycle.    |

Example output:

```yaml
completedCycles: []
ongoingCycle:
  friendlyTimeToResolution: 3h
```

## Jira Watchers

### jira_get_issue_watchers

Description:
Get watchers for a Jira issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: ENG-123
```

Output schema:

| Field      | Type          | Required | Description                           |
| ---------- | ------------- | -------- | ------------------------------------- |
| isWatching | boolean       | No       | Whether the current user is watching. |
| watchCount | integer       | No       | Number of watchers.                   |
| watchers   | array<object> | No       | Watcher records.                      |

Example output:

```yaml
isWatching: true
watchCount: 2
watchers:
  - displayName: Jane Doe
```

### jira_add_watcher

Description:
Add a watcher to a Jira issue.

Input schema:

| Parameter       | Type   | Required | Description                                               |
| --------------- | ------ | -------- | --------------------------------------------------------- |
| issue_key       | string | Yes      | Target issue key.                                         |
| user_identifier | string | Yes      | Account id on Cloud or username on Server or Data Center. |

Example input:

```yaml
issue_key: ENG-123
user_identifier: 5b10ac8d82e05b22cc7d4ef5
```

Output schema:

| Field  | Type   | Required | Description         |
| ------ | ------ | -------- | ------------------- |
| status | string | No       | Add-watcher status. |

Example output:

```yaml
status: updated
```

### jira_remove_watcher

Description:
Remove a watcher from a Jira issue.

Input schema:

| Parameter  | Type   | Required | Description                        |
| ---------- | ------ | -------- | ---------------------------------- |
| issue_key  | string | Yes      | Target issue key.                  |
| username   | string | No       | Username on Server or Data Center. |
| account_id | string | No       | Account id on Cloud.               |

Example input:

```yaml
issue_key: ENG-123
account_id: 5b10ac8d82e05b22cc7d4ef5
```

Output schema:

| Field  | Type   | Required | Description            |
| ------ | ------ | -------- | ---------------------- |
| status | string | No       | Remove-watcher status. |

Example output:

```yaml
status: updated
```

## Jira Forms

### jira_get_issue_proforma_forms

Description:
Get Jira Forms attached to an issue.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |

Example input:

```yaml
issue_key: ENG-123
```

Output schema:

| Field     | Type          | Required | Description               |
| --------- | ------------- | -------- | ------------------------- |
| issue_key | string        | Yes      | Target issue key.         |
| count     | integer       | Yes      | Number of forms returned. |
| forms     | array<object> | Yes      | Form records.             |

Example output:

```yaml
issue_key: ENG-123
count: 1
forms:
  - id: 70001
    name: Incident Review
```

### jira_get_proforma_form_details

Description:
Get details for a specific Jira form.

Input schema:

| Parameter | Type   | Required | Description       |
| --------- | ------ | -------- | ----------------- |
| issue_key | string | Yes      | Target issue key. |
| form_id   | string | Yes      | Form id.          |

Example input:

```yaml
issue_key: ENG-123
form_id: 70001
```

Output schema:

| Field     | Type   | Required | Description           |
| --------- | ------ | -------- | --------------------- |
| issue_key | string | Yes      | Target issue key.     |
| form_id   | string | Yes      | Requested form id.    |
| details   | object | Yes      | Form details payload. |

Example output:

```yaml
issue_key: ENG-123
form_id: 70001
details:
  name: Incident Review
```

### jira_update_proforma_form_answers

Description:
Update answers for a Jira form attached to an issue.

Input schema:

| Parameter | Type          | Required | Description                                       |
| --------- | ------------- | -------- | ------------------------------------------------- |
| issue_key | string        | Yes      | Target issue key.                                 |
| form_id   | string        | Yes      | Form id.                                          |
| answers   | array<object> | Yes      | List of answer objects accepted by the forms API. |

Example input:

```yaml
issue_key: ENG-123
form_id: 70001
answers:
  - fieldKey: impact
    value: medium
```

Output schema:

| Field     | Type   | Required | Description                |
| --------- | ------ | -------- | -------------------------- |
| issue_key | string | Yes      | Target issue key.          |
| form_id   | string | Yes      | Updated form id.           |
| status    | string | Yes      | Update status.             |
| result    | object | Yes      | Provider response payload. |

Example output:

```yaml
issue_key: ENG-123
form_id: 70001
status: updated
result:
  ok: true
```

## Jira Development Info

### jira_get_issue_development_info

Description:
Get development metadata for a single Jira issue.

Input schema:

| Parameter        | Type   | Required | Description                              |
| ---------------- | ------ | -------- | ---------------------------------------- |
| issue_key        | string | Yes      | Target issue key.                        |
| application_type | string | No       | Optional development integration filter. |
| data_type        | string | No       | Optional development data filter.        |

Example input:

```yaml
issue_key: ENG-123
application_type: github
```

Output schema:

| Field  | Type          | Required | Description                          |
| ------ | ------------- | -------- | ------------------------------------ |
| detail | array<object> | No       | Development metadata detail records. |

Example output:

```yaml
detail:
  - branches: 1
    pullRequests: 2
```

### jira_get_issues_development_info

Description:
Get aggregate development metadata for multiple Jira issues.

Input schema:

| Parameter        | Type          | Required | Description                              |
| ---------------- | ------------- | -------- | ---------------------------------------- |
| issue_keys       | array<string> | Yes      | Jira issue keys to inspect.              |
| application_type | string        | No       | Optional development integration filter. |
| data_type        | string        | No       | Optional development data filter.        |

Example input:

```yaml
issue_keys:
  - ENG-123
  - ENG-124
application_type: github
```

Output schema:

| Field  | Type          | Required | Description                                    |
| ------ | ------------- | -------- | ---------------------------------------------- |
| detail | array<object> | No       | Aggregate development metadata detail records. |

Example output:

```yaml
detail:
  - issueKey: ENG-123
    pullRequests: 2
  - issueKey: ENG-124
    pullRequests: 1
```

## Jira Attachments and Images

### jira_download_attachments

Description:
Get Jira issue attachments with optional inline base64 content.

Input schema:

| Parameter        | Type    | Required | Description                                                       |
| ---------------- | ------- | -------- | ----------------------------------------------------------------- |
| issue_key        | string  | Yes      | Target issue key.                                                 |
| include_content  | boolean | No       | Whether to inline base64 content for small files. Default: false. |
| max_inline_bytes | integer | No       | Inline size limit. Default: 2000000.                              |

Example input:

```yaml
issue_key: ENG-123
include_content: false
```

Output schema:

| Field       | Type          | Required | Description                     |
| ----------- | ------------- | -------- | ------------------------------- |
| issue_key   | string        | Yes      | Target issue key.               |
| count       | integer       | Yes      | Number of attachments returned. |
| attachments | array<object> | Yes      | Attachment metadata entries.    |

Example output:

```yaml
issue_key: ENG-123
count: 1
attachments:
  - id: 90001
    filename: screenshot.png
    mime_type: image/png
    size: 12345
```

### jira_get_issue_images

Description:
Get image attachments for a Jira issue with optional inline base64 content.

Input schema:

| Parameter        | Type    | Required | Description                                                        |
| ---------------- | ------- | -------- | ------------------------------------------------------------------ |
| issue_key        | string  | Yes      | Target issue key.                                                  |
| include_content  | boolean | No       | Whether to inline base64 content for small images. Default: false. |
| max_inline_bytes | integer | No       | Inline size limit. Default: 2000000.                               |

Example input:

```yaml
issue_key: ENG-123
include_content: false
```

Output schema:

| Field     | Type          | Required | Description                |
| --------- | ------------- | -------- | -------------------------- |
| issue_key | string        | Yes      | Target issue key.          |
| count     | integer       | Yes      | Number of images returned. |
| images    | array<object> | Yes      | Image attachment entries.  |

Example output:

```yaml
issue_key: ENG-123
count: 1
images:
  - id: 90001
    filename: screenshot.png
    mime_type: image/png
```

## Confluence Pages and Search

### confluence_search

Description:
Search Confluence using free text or a raw CQL expression.

Input schema:

| Parameter | Type    | Required | Description                             |
| --------- | ------- | -------- | --------------------------------------- |
| query     | string  | No       | Free-text search query.                 |
| cql       | string  | No       | Raw CQL expression.                     |
| limit     | integer | No       | Maximum results to return. Default: 10. |

Example input:

```yaml
query: runbook
limit: 5
```

Output schema:

| Field  | Type          | Required | Description                        |
| ------ | ------------- | -------- | ---------------------------------- |
| result | array<object> | Yes      | Compact Confluence search results. |

Example output:

```yaml
- id: 12345
  title: Incident Runbook
  type: page
```

### confluence_get_page

Description:
Fetch a Confluence page by page id.

Input schema:

| Parameter | Type   | Required | Description                                                      |
| --------- | ------ | -------- | ---------------------------------------------------------------- |
| page_id   | string | Yes      | Confluence page id.                                              |
| expand    | string | No       | Confluence expand string. Default: `body.storage,version,space`. |

Example input:

```yaml
page_id: 12345
```

Output schema:

| Field   | Type   | Required | Description            |
| ------- | ------ | -------- | ---------------------- |
| id      | string | No       | Confluence page id.    |
| title   | string | No       | Page title.            |
| body    | object | No       | Page body payload.     |
| version | object | No       | Page version metadata. |

Example output:

```yaml
id: 12345
title: Incident Runbook
version:
  number: 7
```

### confluence_create_page

Description:
Create a Confluence page using storage-format content.

Input schema:

| Parameter      | Type   | Required | Description                  |
| -------------- | ------ | -------- | ---------------------------- |
| space_key      | string | Yes      | Target space key.            |
| title          | string | Yes      | Page title.                  |
| content        | string | Yes      | Storage-format body content. |
| parent_page_id | string | No       | Optional parent page id.     |

Example input:

```yaml
space_key: ENG
title: New Runbook
content: <p>Runbook content</p>
```

Output schema:

| Field  | Type   | Required | Description                 |
| ------ | ------ | -------- | --------------------------- |
| status | string | Yes      | Creation status.            |
| page   | object | Yes      | Compact created-page block. |

Example output:

```yaml
status: created
page:
  id: 20001
  title: New Runbook
  type: page
```

### confluence_update_page

Description:
Update a Confluence page and increment its version.

Input schema:

| Parameter | Type   | Required | Description                  |
| --------- | ------ | -------- | ---------------------------- |
| page_id   | string | Yes      | Target page id.              |
| content   | string | Yes      | Updated storage-format body. |
| title     | string | No       | Optional replacement title.  |

Example input:

```yaml
page_id: 20001
content: <p>Updated runbook content</p>
title: Updated Runbook
```

Output schema:

| Field  | Type   | Required | Description                 |
| ------ | ------ | -------- | --------------------------- |
| status | string | Yes      | Update status.              |
| page   | object | Yes      | Compact updated-page block. |

Example output:

```yaml
status: updated
page:
  id: 20001
  title: Updated Runbook
  version: 8
```

### confluence_delete_page

Description:
Delete a Confluence page by id.

Input schema:

| Parameter | Type   | Required | Description     |
| --------- | ------ | -------- | --------------- |
| page_id   | string | Yes      | Target page id. |

Example input:

```yaml
page_id: 20001
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Delete status when returned by the API. |

Example output:

```yaml
status: deleted
```

### confluence_get_page_children

Description:
List direct child pages for a Confluence page.

Input schema:

| Parameter | Type    | Required | Description                                 |
| --------- | ------- | -------- | ------------------------------------------- |
| page_id   | string  | Yes      | Parent page id.                             |
| limit     | integer | No       | Maximum child pages to return. Default: 25. |

Example input:

```yaml
page_id: 12345
limit: 10
```

Output schema:

| Field  | Type          | Required | Description         |
| ------ | ------------- | -------- | ------------------- |
| result | array<object> | Yes      | Child page records. |

Example output:

```yaml
- id: 12346
  title: Child Page
  type: page
  status: current
```

### confluence_search_user

Description:
Search Confluence users by full name.

Input schema:

| Parameter | Type    | Required | Description                           |
| --------- | ------- | -------- | ------------------------------------- |
| query     | string  | Yes      | Name query.                           |
| limit     | integer | No       | Maximum users to return. Default: 10. |

Example input:

```yaml
query: Jane
limit: 3
```

Output schema:

| Field | Type          | Required | Description               |
| ----- | ------------- | -------- | ------------------------- |
| query | string        | Yes      | Echoed search query.      |
| count | integer       | Yes      | Number of users returned. |
| users | array<object> | Yes      | Matching user records.    |

Example output:

```yaml
query: Jane
count: 1
users:
  - displayName: Jane Doe
```

## Confluence Comments and Labels

### confluence_get_comments

Description:
Get comments for a Confluence page.

Input schema:

| Parameter | Type    | Required | Description                              |
| --------- | ------- | -------- | ---------------------------------------- |
| page_id   | string  | Yes      | Target page id.                          |
| limit     | integer | No       | Maximum comments to return. Default: 25. |

Example input:

```yaml
page_id: 12345
limit: 5
```

Output schema:

| Field    | Type          | Required | Description                  |
| -------- | ------------- | -------- | ---------------------------- |
| page_id  | string        | Yes      | Target page id.              |
| count    | integer       | Yes      | Number of comments returned. |
| comments | array<object> | Yes      | Comment records.             |

Example output:

```yaml
page_id: 12345
count: 1
comments:
  - id: 81001
    type: comment
```

### confluence_add_comment

Description:
Add a comment to a Confluence page using storage-format content.

Input schema:

| Parameter | Type   | Required | Description                  |
| --------- | ------ | -------- | ---------------------------- |
| page_id   | string | Yes      | Target page id.              |
| body      | string | Yes      | Storage-format comment body. |

Example input:

```yaml
page_id: 12345
body: <p>Please update the owner section.</p>
```

Output schema:

| Field   | Type   | Required | Description                    |
| ------- | ------ | -------- | ------------------------------ |
| status  | string | Yes      | Creation status.               |
| comment | object | Yes      | Compact created-comment block. |

Example output:

```yaml
status: created
comment:
  id: 81002
  type: comment
```

### confluence_get_labels

Description:
Get labels attached to a Confluence page.

Input schema:

| Parameter | Type   | Required | Description     |
| --------- | ------ | -------- | --------------- |
| page_id   | string | Yes      | Target page id. |

Example input:

```yaml
page_id: 12345
```

Output schema:

| Field   | Type          | Required | Description                |
| ------- | ------------- | -------- | -------------------------- |
| page_id | string        | Yes      | Target page id.            |
| count   | integer       | Yes      | Number of labels returned. |
| labels  | array<object> | Yes      | Label records.             |

Example output:

```yaml
page_id: 12345
count: 2
labels:
  - name: runbook
```

### confluence_add_label

Description:
Add a label to a Confluence page.

Input schema:

| Parameter | Type   | Required | Description     |
| --------- | ------ | -------- | --------------- |
| page_id   | string | Yes      | Target page id. |
| name      | string | Yes      | Label name.     |

Example input:

```yaml
page_id: 12345
name: runbook
```

Output schema:

| Field   | Type          | Required | Description              |
| ------- | ------------- | -------- | ------------------------ |
| status  | string        | Yes      | Creation status.         |
| page_id | string        | Yes      | Target page id.          |
| labels  | array<object> | Yes      | Resulting label records. |

Example output:

```yaml
status: created
page_id: 12345
labels:
  - name: runbook
```

## Confluence Attachments and Images

### confluence_get_attachments

Description:
List attachments for a Confluence page or blog post with optional filtering.

Input schema:

| Parameter  | Type    | Required | Description                             |
| ---------- | ------- | -------- | --------------------------------------- |
| content_id | string  | Yes      | Page or blog content id.                |
| start      | integer | No       | Pagination offset. Default: 0.          |
| limit      | integer | No       | Maximum results to return. Default: 50. |
| filename   | string  | No       | Optional filename filter.               |
| media_type | string  | No       | Optional media-type filter.             |

Example input:

```yaml
content_id: 12345
limit: 10
media_type: image/png
```

Output schema:

| Field       | Type          | Required | Description                     |
| ----------- | ------------- | -------- | ------------------------------- |
| content_id  | string        | Yes      | Requested content id.           |
| start       | integer       | Yes      | Pagination offset.              |
| limit       | integer       | Yes      | Page size.                      |
| count       | integer       | Yes      | Number of attachments returned. |
| attachments | array<object> | Yes      | Compact attachment metadata.    |

Example output:

```yaml
content_id: 12345
start: 0
limit: 10
count: 1
attachments:
  - id: att001
    title: diagram.png
    media_type: image/png
```

### confluence_download_attachment

Description:
Get Confluence attachment metadata and optionally inline file content as base64.

Input schema:

| Parameter        | Type    | Required | Description                                            |
| ---------------- | ------- | -------- | ------------------------------------------------------ |
| attachment_id    | string  | Yes      | Attachment id.                                         |
| include_content  | boolean | No       | Whether to inline base64 file content. Default: false. |
| max_inline_bytes | integer | No       | Inline size limit. Default: 2000000.                   |

Example input:

```yaml
attachment_id: att001
include_content: false
```

Output schema:

| Field          | Type    | Required | Description                                            |
| -------------- | ------- | -------- | ------------------------------------------------------ |
| id             | string  | Yes      | Attachment id.                                         |
| title          | string  | No       | Attachment title.                                      |
| media_type     | string  | No       | Attachment media type.                                 |
| file_size      | integer | No       | Attachment size in bytes.                              |
| download       | string  | No       | Download URL fragment.                                 |
| content_base64 | string  | No       | Inline base64 content when requested and small enough. |

Example output:

```yaml
id: att001
title: diagram.png
media_type: image/png
file_size: 12345
download: /download/attachments/12345/diagram.png
```

### confluence_download_content_attachments

Description:
Download attachment metadata for a page or blog post and optionally inline small file content.

Input schema:

| Parameter        | Type    | Required | Description                                            |
| ---------------- | ------- | -------- | ------------------------------------------------------ |
| content_id       | string  | Yes      | Page or blog content id.                               |
| include_content  | boolean | No       | Whether to inline base64 file content. Default: false. |
| max_files        | integer | No       | Maximum attachments to inspect. Default: 20.           |
| max_inline_bytes | integer | No       | Inline size limit. Default: 2000000.                   |

Example input:

```yaml
content_id: 12345
include_content: false
max_files: 5
```

Output schema:

| Field       | Type          | Required | Description                     |
| ----------- | ------------- | -------- | ------------------------------- |
| content_id  | string        | Yes      | Requested content id.           |
| count       | integer       | Yes      | Number of attachments returned. |
| attachments | array<object> | Yes      | Attachment payloads.            |

Example output:

```yaml
content_id: 12345
count: 1
attachments:
  - id: att001
    title: diagram.png
```

### confluence_get_page_images

Description:
List image attachments for a Confluence page or blog post with optional inline content.

Input schema:

| Parameter        | Type    | Required | Description                                             |
| ---------------- | ------- | -------- | ------------------------------------------------------- |
| content_id       | string  | Yes      | Page or blog content id.                                |
| include_content  | boolean | No       | Whether to inline base64 image content. Default: false. |
| max_inline_bytes | integer | No       | Inline size limit. Default: 2000000.                    |

Example input:

```yaml
content_id: 12345
include_content: false
```

Output schema:

| Field      | Type          | Required | Description                           |
| ---------- | ------------- | -------- | ------------------------------------- |
| content_id | string        | Yes      | Requested content id.                 |
| count      | integer       | Yes      | Number of image attachments returned. |
| images     | array<object> | Yes      | Image attachment payloads.            |

Example output:

```yaml
content_id: 12345
count: 1
images:
  - id: att001
    title: diagram.png
    media_type: image/png
```

### confluence_upload_attachment

Description:
Upload a single attachment to a Confluence page or blog post from base64 content.

Input schema:

| Parameter      | Type   | Required | Description                  |
| -------------- | ------ | -------- | ---------------------------- |
| content_id     | string | Yes      | Page or blog content id.     |
| file_name      | string | Yes      | File name to store.          |
| content_base64 | string | Yes      | Base64-encoded file content. |
| media_type     | string | No       | Optional media type.         |
| comment        | string | No       | Optional attachment comment. |

Example input:

```yaml
content_id: 12345
file_name: diagram.png
content_base64: iVBORw0KGgoAAAANSUhEUgAAAAUA
media_type: image/png
```

Output schema:

| Field       | Type          | Required | Description                              |
| ----------- | ------------- | -------- | ---------------------------------------- |
| content_id  | string        | Yes      | Requested content id.                    |
| count       | integer       | Yes      | Number of uploaded attachments returned. |
| attachments | array<object> | Yes      | Uploaded attachment records.             |

Example output:

```yaml
content_id: 12345
count: 1
attachments:
  - id: att001
    title: diagram.png
    media_type: image/png
```

### confluence_upload_attachments

Description:
Upload multiple attachments from a list of base64 payloads.

Input schema:

| Parameter  | Type          | Required | Description                                                                                                         |
| ---------- | ------------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| content_id | string        | Yes      | Page or blog content id.                                                                                            |
| files      | array<object> | Yes      | List of file payloads with `file_name` and `content_base64`; each item may also include `media_type` and `comment`. |

Example input:

```yaml
content_id: 12345
files:
  - file_name: diagram.png
    content_base64: iVBORw0KGgoAAAANSUhEUgAAAAUA
    media_type: image/png
  - file_name: notes.txt
    content_base64: SGVsbG8=
    media_type: text/plain
```

Output schema:

| Field       | Type          | Required | Description                                    |
| ----------- | ------------- | -------- | ---------------------------------------------- |
| content_id  | string        | Yes      | Requested content id.                          |
| count       | integer       | Yes      | Total uploaded attachments across all entries. |
| attachments | array<object> | Yes      | Flattened uploaded attachment records.         |

Example output:

```yaml
content_id: 12345
count: 2
attachments:
  - id: att001
    title: diagram.png
  - id: att002
    title: notes.txt
```

### confluence_delete_attachment

Description:
Delete a Confluence attachment by id.

Input schema:

| Parameter     | Type   | Required | Description              |
| ------------- | ------ | -------- | ------------------------ |
| attachment_id | string | Yes      | Attachment id to delete. |

Example input:

```yaml
attachment_id: att001
```

Output schema:

| Field  | Type   | Required | Description                             |
| ------ | ------ | -------- | --------------------------------------- |
| status | string | No       | Delete status when returned by the API. |

Example output:

```yaml
status: deleted
```

## Resource

### atlassian://config

Description:
Return a non-secret runtime configuration summary for the MCP server.

Input schema:

| Parameter | Type | Required | Description                                                            |
| --------- | ---- | -------- | ---------------------------------------------------------------------- |
| none      | none | Yes      | This is an MCP resource, not a tool, and it does not accept arguments. |

Example input:

```yaml
{}
```

Output schema:

| Field     | Type          | Required | Description                              |
| --------- | ------------- | -------- | ---------------------------------------- |
| server    | object        | No       | Runtime server metadata.                 |
| toolsets  | array<string> | No       | Visible toolsets in the current process. |
| endpoints | object        | No       | Non-secret base URL summary.             |

Example output:

```yaml
server:
  name: Atlassian
toolsets:
  - core
  - jira-read
endpoints:
  jira_base_url: https://jira.example.com
  confluence_base_url: https://wiki.example.com
```

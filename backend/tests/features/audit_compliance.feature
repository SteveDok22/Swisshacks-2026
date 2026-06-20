Feature: Audit Log Compliance

  Scenario: Customer drift analysis writes an audit entry
    Given the drift engine has customers
    When an officer requests the full analysis for the top customer
    Then an audit entry with event_type "drift_subject_analyzed" exists
    And the audit entry contains a risk_score

  Scenario: Audit log is append-only by design
    When I inspect the AuditService interface
    Then no "update" method exists on AuditService
    And no "delete" method exists on AuditService

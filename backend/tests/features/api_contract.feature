Feature: API Contract

  Scenario: Customer list is sorted by drift score descending
    When I call GET "/api/v1/drift/customers"
    Then the response status is 200
    And customers are sorted by drift_score descending

  Scenario: Unknown customer returns 404
    When I call GET "/api/v1/drift/customers/nonexistent-xyz-abc"
    Then the response status is 404

  Scenario: Cascade scan returns a valid cost report
    When I call POST "/api/v1/drift/scan"
    Then the response status is 200
    And the response body contains "total_customers"
    And the response body contains "savings_pct"

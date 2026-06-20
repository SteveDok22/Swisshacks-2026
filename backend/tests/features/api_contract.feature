Feature: API Contract

  Scenario: Subject list is sorted by drift score descending
    When I call GET "/api/v1/drift/subjects"
    Then the response status is 200
    And subjects are sorted by drift_score descending

  Scenario: Unknown subject returns 404
    When I call GET "/api/v1/drift/subjects/nonexistent-xyz-abc"
    Then the response status is 404

  Scenario: Subject detail exposes business-model drift fields
    When I call GET "/api/v1/drift/subjects/drift-001"
    Then the response status is 200
    And the response body contains "is_business_model_change"
    And the response body contains "business_model_distance"

  Scenario: Cascade scan returns a valid cost report
    When I call POST "/api/v1/drift/scan"
    Then the response status is 200
    And the response body contains "total_customers"
    And the response body contains "savings_pct"

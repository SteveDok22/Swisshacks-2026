Feature: KYC Drift Detection

  Scenario: Benign expansion is classified as benign
    Given the "benign_expansion" synthetic customer with seed 42
    When causal assessment is run on the customer
    Then the causal label is "benign"

  Scenario: Risk-shaped change is classified as risk
    Given the "combined" synthetic customer with seed 42
    When causal assessment is run on the customer
    Then the causal label is "risk"

  Scenario: Slow-walker is flagged despite low absolute drift
    Given the "suspicious_stability" synthetic customer with seed 42
    And the book cohort volatility is computed
    When stability is assessed with the customer's environment
    Then is_suspicious is true

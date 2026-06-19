Feature: Ownership Contagion

  Scenario: Direct owner of sanctioned entity is elevated
    Given a sanctioned seed entity "seed-corp"
    And a customer "cust-001" who is directly connected to the seed
    When contagion is propagated from the seed
    Then the customer "cust-001" has propagated_risk above 0.1

  Scenario: Far connection receives less risk than direct connection
    Given a sanctioned seed entity "seed-corp"
    And a customer "cust-near" one hop from the seed
    And a customer "cust-far" two hops from the seed
    When contagion is propagated from the seed
    Then the customer "cust-near" has higher propagated_risk than "cust-far"

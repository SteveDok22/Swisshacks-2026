Feature: Time-Travel Audit (no look-ahead bias)

  The regulator's question is whether an escalation was fitted after the fact.
  The as-of replay answers it: freeze time at month T and recompute the score
  using ONLY data available up to and including T. If the system would already
  have alerted before the sanctions listing — without seeing the future — the
  lead time is real, not hindsight.

  Scenario: As-of replay never uses data from after the as-of month
    Given the "combined" drift customer wired to a sanctions listing
    When the score is replayed as of a month before the listing
    Then the replay uses no public signal dated after that month
    And contagion risk is inactive before the listing month

  Scenario: Replay alerts before the sanctions listing with positive lead time
    Given the "combined" drift customer wired to a sanctions listing
    When the full as-of trajectory is replayed
    Then the alert month precedes the sanctions month
    And the lead time is positive

  Scenario: As-of score at a month is independent of any future months
    Given the "combined" drift customer wired to a sanctions listing
    When the as-of score at a month is recomputed from a future-truncated history
    Then the two as-of scores are identical

Feature: Attendances (join, cancel, list, check, my attendances)

  Scenario: Join a scheduled route call
    Given I am an authenticated user
    And a SCHEDULED route call exists
    When I POST my attendance to that route call
    Then the response status is 201
    And my attendance status is "CONFIRMED"

  Scenario: Cannot join a cancelled route call
    Given I am an authenticated user
    And the route call is CANCELLED
    When I POST my attendance
    Then the response status is 400

  Scenario: Cannot join twice
    Given I already have a CONFIRMED attendance for the route call
    When I POST my attendance again
    Then the response status is 409

  Scenario: Re-join after cancelling reactivates the attendance
    Given I previously cancelled my attendance for the route call
    When I POST my attendance again
    Then the response status is 201
    And my attendance status is "CONFIRMED"

  Scenario: Reject an unauthenticated request
    Given I am not authenticated
    When I POST my attendance
    Then the response status is 401

  Scenario: Cancel my confirmed attendance
    Given I have a CONFIRMED attendance for the route call
    When I DELETE my attendance
    Then the response status is 200
    And my attendance status is "CANCELLED"

  Scenario: Cannot cancel when I am not attending
    Given I have no attendance for the route call
    When I DELETE my attendance
    Then the response status is 404

  Scenario: Cannot cancel an already cancelled attendance
    Given my attendance is already CANCELLED
    When I DELETE my attendance
    Then the response status is 400

  Scenario: List confirmed attendees of a route call
    Given a route call has several confirmed attendees
    When I GET the attendances of that route call
    Then the response status is 200
    And only CONFIRMED attendees are returned

  Scenario: List attendees of a non-existent route call
    When I GET the attendances of a random valid UUID
    Then the response status is 404

  Scenario: Check returns true when I am confirmed
    Given I have a CONFIRMED attendance for the route call
    When I GET the attendance check
    Then the response status is 200
    And isAttending is true

  Scenario: Check returns false when I am not attending
    Given I have no active attendance for the route call
    When I GET the attendance check
    Then isAttending is false

  Scenario: List my confirmed attendances
    Given I am an authenticated user with several confirmed attendances
    When I GET my attendances
    Then the response status is 200
    And only my CONFIRMED attendances are returned

  Scenario: Re-joining reuses the same attendance record
    Given I have a CANCELLED attendance for the route call
    When I join again
    Then the same attendance record is reused with status "CONFIRMED"
    And no duplicate attendance is created

  Scenario: Reject an invalid route call id
    Given I am an authenticated user
    When I POST my attendance to a non-UUID route call id
    Then the response status is 400

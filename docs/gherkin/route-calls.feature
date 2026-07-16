Feature: Route calls (create, list, detail, update, cancel, delete)

  Scenario: Successfully create a route call on a predefined route
    Given I am an authenticated user
    And a predefined route exists
    When I POST a route call with that routeId, a future dateRoute, one pace and one PRIMARY meeting point
    Then the response status is 201
    And the route call status is "SCHEDULED"
    And the response includes the organizer and the meeting points

  Scenario: Create a custom route call without a title
    Given I am an authenticated user
    When I POST a route call with no routeId and no title
    Then the response status is 400
    And the error message is "Title is required for custom routes"

  Scenario: Reject a route call scheduled in the past
    Given I am an authenticated user
    When I POST a route call with a dateRoute in the past
    Then the response status is 400

  Scenario: Reject invalid meeting points
    Given I am an authenticated user
    When I POST a route call with zero PRIMARY meeting points
    Then the response status is 400

  Scenario: Reject an unauthenticated request
    Given I am not authenticated
    When I POST a route call
    Then the response status is 401

  Scenario: List upcoming route calls with pagination
    Given several route calls exist
    When I GET route calls with upcoming=true and limit=10
    Then the response status is 200
    And the data contains only SCHEDULED or ONGOING route calls
    And the response includes a pagination block

  Scenario: Reject an invalid month filter
    When I GET route calls with month "2026-13"
    Then the response status is 400

  Scenario: Get an existing route call
    Given a route call exists with a known id
    When I GET that route call by id
    Then the response status is 200
    And the data includes the organizer, meeting points and confirmed attendance count

  Scenario: Get a non-existent route call
    When I GET a route call with a random valid UUID
    Then the response status is 404

  Scenario: Organizer updates a scheduled route call
    Given I am the organizer of a SCHEDULED route call
    When I PATCH new title and paces
    Then the response status is 200
    And the route call reflects the new values

  Scenario: A non-organizer cannot update
    Given I am authenticated but not the organizer
    When I PATCH changes to the route call
    Then the response status is 403

  Scenario: A non-organizer updating a completed route call gets 403
    Given I am authenticated but not the organizer
    And the route call is COMPLETED
    When I PATCH changes to the route call
    Then the response status is 403

  Scenario: Reject an update with a past dateRoute
    Given I am the organizer of a SCHEDULED route call
    When I PATCH a dateRoute in the past
    Then the response status is 400

  Scenario: Cannot update a completed route call
    Given I am the organizer of a COMPLETED route call
    When I PATCH changes
    Then the response status is 400

  Scenario: Cannot update an ongoing route call
    Given I am the organizer of an ONGOING route call
    When I PATCH changes
    Then the response status is 400

  Scenario: Organizer cancels a scheduled route call
    Given I am the organizer of a SCHEDULED route call
    When I PATCH it to cancel
    Then the response status is 200
    And the route call status is "CANCELLED"

  Scenario: Admin cancels someone else route call
    Given I am an admin and not the organizer
    When I PATCH the route call to cancel
    Then the response status is 200

  Scenario: Cannot cancel an already cancelled route call
    Given a route call is already CANCELLED
    When I PATCH it to cancel
    Then the response status is 400

  Scenario: Admin deletes a route call with no attendances
    Given I am an admin
    And the route call has zero attendances
    When I DELETE the route call
    Then the response status is 200

  Scenario: Cannot delete a route call that has attendances
    Given I am the organizer
    And the route call has at least one confirmed attendance
    When I DELETE the route call
    Then the response status is 400
    And the error suggests cancelling it instead

  Scenario: A normal non-organizer user cannot delete
    Given I am authenticated, not the organizer and not an admin
    When I DELETE the route call
    Then the response status is 403

  Scenario: Validation error keeps the response envelope
    When I POST a route call with an invalid paces value
    Then the response status is 400
    And the body has success=false and an error message

  Scenario: Successful responses use the standard envelope
    When I GET the list of route calls
    Then the body has success=true and a data array

  Scenario: A scheduled route call becomes ongoing at its start time
    Given a SCHEDULED route call whose dateRoute has just arrived
    When the scheduler runs
    Then the route call status becomes "ONGOING"

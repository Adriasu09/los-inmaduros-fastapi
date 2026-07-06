Feature: Reviews (create, list, my reviews, update, delete with admin moderation)

  Scenario: List reviews of a route
    Given a route has several reviews
    When I GET the reviews of that route
    Then the response status is 200
    And the reviews are ordered from newest to oldest
    And the response includes pagination metadata

  Scenario: List reviews of a non-existent route
    When I GET the reviews of an unknown route id
    Then the response status is 404

  Scenario: Create a review for a route
    Given I am an authenticated user
    And I have not reviewed this route yet
    When I POST a review with a rating of 4 and a comment
    Then the response status is 201
    And the review belongs to me and to the route

  Scenario: Cannot review the same route twice
    Given I have already reviewed this route
    When I POST another review for the same route
    Then the response status is 409

  Scenario: Reject an out-of-range rating
    Given I am an authenticated user
    When I POST a review with a rating of 6
    Then the response status is 400

  Scenario: Reject an invalid rating type
    Given I am an authenticated user
    When I POST a review with a non-integer rating
    Then the response status is 400

  Scenario: Reject an unauthenticated review
    Given I am not authenticated
    When I POST a review
    Then the response status is 401

  Scenario: List my reviews
    Given I am an authenticated user with several reviews
    When I GET my reviews
    Then the response status is 200
    And only my reviews are returned, newest first

  Scenario: Edit my own review
    Given I am the author of a review
    When I PUT a new rating and comment
    Then the response status is 200
    And the review reflects the new values

  Scenario: Cannot edit a review from another user
    Given a review authored by another user
    When I PUT changes to it
    Then the response status is 403

  Scenario: Edit a non-existent review
    When I PUT changes to an unknown review id
    Then the response status is 404

  Scenario: Delete my own review
    Given I am the author of a review
    When I DELETE the review
    Then the response status is 200
    And the review no longer exists

  Scenario: A non-admin cannot delete a review from another user
    Given a review authored by another user
    And I am not an admin
    When I DELETE it
    Then the response status is 403

  Scenario: An admin can delete any review
    Given a review authored by another user
    And I am an admin
    When I DELETE it
    Then the response status is 200

  Scenario: Enforce one review per user and route
    Given I already have a review for the route
    When I try to create another one
    Then the operation is rejected with a conflict error

Feature: Favorites (add, remove, list, check)

  Scenario: Add a route to my favorites
    Given I am an authenticated user
    And the route is not in my favorites yet
    When I POST the route to my favorites
    Then the response status is 201

  Scenario: Cannot favorite the same route twice
    Given the route is already in my favorites
    When I POST it to my favorites again
    Then the response status is 409

  Scenario: Cannot favorite a non-existent route
    Given I am an authenticated user
    When I POST an unknown route id to my favorites
    Then the response status is 404

  Scenario: Reject an unauthenticated request
    Given I am not authenticated
    When I POST a route to favorites
    Then the response status is 401

  Scenario: Remove a route from my favorites
    Given the route is in my favorites
    When I DELETE it from my favorites
    Then the response status is 200

  Scenario: Cannot remove a route that is not in my favorites
    Given the route is not in my favorites
    When I DELETE it from my favorites
    Then the response status is 404

  Scenario: List my favorite routes
    Given I am an authenticated user with several favorite routes
    When I GET my favorites
    Then the response status is 200
    And my favorite routes are returned, newest first

  Scenario: Check returns true when the route is a favorite
    Given the route is in my favorites
    When I GET the favorite check for that route
    Then the response status is 200
    And isFavorite is true

  Scenario: Check returns false when the route is not a favorite
    Given the route is not in my favorites
    When I GET the favorite check for that route
    Then isFavorite is false

  Scenario: Enforce one favorite per user and route
    Given the route is already in my favorites
    When I try to add it again
    Then the operation is rejected with a conflict error

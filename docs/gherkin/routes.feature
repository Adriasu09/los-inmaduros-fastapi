Feature: Routes (read-only catalogue and detail)

  Scenario: List all predefined routes
    Given predefined routes exist
    When I GET the routes catalogue
    Then the response status is 200
    And the routes are ordered by name ascending
    And each route includes its average rating and its counts

  Scenario: Get a route detail by slug
    Given a route with a known slug exists
    When I GET that route by slug
    Then the response status is 200
    And the data includes description, levels, map and gpx info, average rating, paginated reviews and active photos

  Scenario: Get a non-existent route
    When I GET a route with an unknown slug
    Then the response status is 404

  Scenario: Paginate the reviews of a route
    Given a route has more than 20 reviews
    When I GET the route with reviewsLimit 10 and reviewsPage 2
    Then only the second page of 10 reviews is returned
    And the response includes review pagination metadata

  Scenario: Only active photos are shown in the route detail
    Given a route has active and non-active photos
    When I GET the route by slug
    Then only ACTIVE photos are returned

  Scenario: Average rating reflects the route reviews
    Given a route has several reviews with different ratings
    When I GET the route
    Then the averageRating equals the mean of its review ratings

  Scenario: Predefined routes are available after seeding
    Given the database has been seeded with predefined routes
    When the application starts
    Then the routes catalogue returns the seeded routes

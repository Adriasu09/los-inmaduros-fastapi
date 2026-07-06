Feature: Authentication (Clerk JWT validation, user sync, dev test token)

  Scenario: Access a protected endpoint with a valid token
    Given I am signed in with Clerk
    When I call a protected endpoint with my Bearer token
    Then the request is authorized and identified as me

  Scenario: Reject a protected endpoint without a token
    Given I do not send an Authorization header
    When I call a protected endpoint
    Then the response status is 401

  Scenario: Reject an admin-only action for a normal user
    Given I am authenticated as a normal user
    When I call an admin-only endpoint
    Then the response status is 403

  Scenario: The dependency rejects an invalid token
    Given a request with an invalid or expired Clerk token
    When it reaches a protected endpoint
    Then get_current_user raises an unauthorized error mapped to 401

  Scenario: A first-time authenticated user is created in the database
    Given a valid Clerk user who has never called the API
    When they make their first authenticated request
    Then a matching user is created in the database with role USER

  Scenario: Generate a test token in development
    Given the app runs in development mode
    And a Clerk user exists with a given email
    When I POST that email to the test-token endpoint
    Then the response status is 200
    And a usable Bearer token is returned

  Scenario: The test-token endpoint is disabled in production
    Given the app runs in production mode
    When I POST to the test-token endpoint
    Then the response status is 404

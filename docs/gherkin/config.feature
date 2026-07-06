Feature: App configuration constants

  Scenario: Get the application configuration
    Given the application is running
    When I GET the config endpoint
    Then the response status is 200
    And the data includes meetingPoints, routePaces and routeLevels

  Scenario: Config values match the enums used across the app
    When I GET the config endpoint
    Then the returned route levels match the RouteLevel enum used elsewhere

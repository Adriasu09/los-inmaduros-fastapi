Feature: Photos (upload with context permissions, galleries, moderation, soft delete)

  Scenario: A confirmed attendee uploads a photo to a route call gallery
    Given I am an authenticated user with a CONFIRMED attendance for the route call
    When I POST a photo with context "ROUTE_CALL_GALLERY" for that route call
    Then the response status is 201
    And the photo status is "ACTIVE"

  Scenario: A non-attendee cannot upload to a route call gallery
    Given I am an authenticated user without a confirmed attendance
    When I POST a photo with context "ROUTE_CALL_GALLERY"
    Then the response status is 403

  Scenario: Only the organizer can upload a cover photo
    Given I am an authenticated user who is not the organizer
    When I POST a photo with context "ROUTE_CALL_COVER"
    Then the response status is 403

  Scenario: Upload a photo to a route gallery
    Given I am an authenticated user
    When I POST a photo with context "ROUTE_GALLERY" and a valid routeId
    Then the response status is 201

  Scenario: Reject providing both routeId and routeCallId
    Given I am an authenticated user
    When I POST a photo with both a routeId and a routeCallId
    Then the response status is 400

  Scenario: Reject an upload with a missing routeId for a route gallery
    Given I am an authenticated user
    When I POST a ROUTE_GALLERY photo without a routeId
    Then the response status is 400

  Scenario: View a route gallery
    Given a route has active and rejected photos
    When I GET the gallery of that route by slug
    Then the response status is 200
    And only ACTIVE photos are returned

  Scenario: View a route call gallery
    Given a route call has active photos
    When I GET the gallery of that route call by id
    Then the response status is 200
    And only ACTIVE photos are returned

  Scenario: Gallery of a non-existent route
    When I GET the gallery of an unknown route slug
    Then the response status is 404

  Scenario: List my photos including rejected ones
    Given I have uploaded several photos, one of them rejected
    When I GET my photos
    Then the response status is 200
    And my non-deleted photos are returned with their status

  Scenario: Organizer sets the cover photo of a route call
    Given I am the organizer of a route call
    When I PATCH a new cover photo as multipart
    Then the response status is 200
    And the route call cover photo is updated

  Scenario: A non-organizer cannot set the cover photo
    Given I am authenticated but not the organizer
    When I PATCH a cover photo
    Then the response status is 403

  Scenario: Author deletes their own photo
    Given I am the author of a photo
    When I DELETE the photo
    Then the response status is 200
    And the photo status is "DELETED"

  Scenario: An admin deletes any photo
    Given I am an admin
    When I DELETE a photo uploaded by another user
    Then the response status is 200

  Scenario: A non-author non-admin cannot delete a photo
    Given I am authenticated, not the author and not an admin
    When I DELETE the photo
    Then the response status is 403

  Scenario: Admin lists photos pending review
    Given there are active photos not yet moderated
    When an admin GETs the pending-review queue
    Then the response status is 200
    And the not-yet-moderated active photos are returned

  Scenario: Admin rejects an inappropriate photo
    Given I am an admin
    When I PATCH a photo to reject it with a moderation note
    Then the response status is 200
    And the photo status is "REJECTED"

  Scenario: A normal user cannot access moderation
    Given I am an authenticated non-admin user
    When I GET the pending-review queue
    Then the response status is 403

  Scenario: Rejected photos disappear from the public gallery
    Given a photo has been rejected
    When I GET the gallery
    Then the rejected photo is not returned

  Scenario: Attendance is required to upload event photos
    Given a user without a confirmed attendance
    When they try to upload a ROUTE_CALL_GALLERY photo
    Then the service raises a forbidden error mapped to 403

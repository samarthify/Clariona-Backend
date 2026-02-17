> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get stream rules

> Retrieves the active rule set or a subset of rules for the filtered stream.



## OpenAPI

````yaml get /2/tweets/search/stream/rules
openapi: 3.0.0
info:
  description: X API v2 available endpoints
  version: '2.157'
  title: X API v2
  termsOfService: https://developer.x.com/en/developer-terms/agreement-and-policy.html
  contact:
    name: X Developers
    url: https://developer.x.com/
  license:
    name: X Developer Agreement and Policy
    url: https://developer.x.com/en/developer-terms/agreement-and-policy.html
servers:
  - description: X API
    url: https://api.x.com
security: []
tags:
  - name: Account Activity
    description: Endpoints relating to retrieving, managing AAA subscriptions
    externalDocs:
      description: Find out more
      url: >-
        https://docs.x.com/x-api/enterprise-gnip-2.0/fundamentals/account-activity
  - name: Bookmarks
    description: Endpoints related to retrieving, managing bookmarks of a user
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/bookmarks
  - name: Compliance
    description: Endpoints related to keeping X data in your systems compliant
    externalDocs:
      description: Find out more
      url: >-
        https://developer.twitter.com/en/docs/twitter-api/compliance/batch-tweet/introduction
  - name: Connections
    description: Endpoints related to streaming connections
    externalDocs:
      description: Find out more
      url: https://developer.x.com/en/docs/x-api/connections
  - name: Direct Messages
    description: Endpoints related to retrieving, managing Direct Messages
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/direct-messages
  - name: General
    description: Miscellaneous endpoints for general API functionality
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api
  - name: Lists
    description: Endpoints related to retrieving, managing Lists
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/lists
  - name: Media
    description: Endpoints related to Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: MediaUpload
    description: Endpoints related to uploading Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: News
    description: Endpoint for retrieving news stories
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/news
  - name: Spaces
    description: Endpoints related to retrieving, managing Spaces
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/spaces
  - name: Stream
    description: Endpoints related to streaming
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: Tweets
    description: Endpoints related to retrieving, searching, and modifying Tweets
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/tweets/lookup
  - name: Users
    description: Endpoints related to retrieving, managing relationships of Users
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/users/lookup
paths:
  /2/tweets/search/stream/rules:
    get:
      tags:
        - Stream
        - Tweets
      summary: Get stream rules
      description: >-
        Retrieves the active rule set or a subset of rules for the filtered
        stream.
      operationId: getRules
      parameters:
        - name: ids
          in: query
          description: A comma-separated list of Rule IDs.
          required: false
          schema:
            type: array
            items:
              $ref: '#/components/schemas/RuleId'
          style: form
        - name: max_results
          in: query
          description: The maximum number of results.
          required: false
          schema:
            type: integer
            minimum: 1
            maximum: 1000
            format: int32
            default: 1000
          style: form
        - name: pagination_token
          in: query
          description: >-
            This value is populated by passing the 'next_token' returned in a
            request to paginate through results.
          required: false
          schema:
            type: string
            minLength: 16
            maxLength: 16
          style: form
      responses:
        '200':
          description: The request has succeeded.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RulesLookupResponse'
        default:
          description: The request has failed.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
            application/problem+json:
              schema:
                $ref: '#/components/schemas/Problem'
      security:
        - BearerToken: []
      externalDocs:
        url: >-
          https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/api-reference/get-tweets-search-stream-rules
components:
  schemas:
    RuleId:
      type: string
      description: Unique identifier of this rule.
      pattern: ^[0-9]{1,19}$
      example: '120897978112909812'
    RulesLookupResponse:
      type: object
      required:
        - meta
      properties:
        data:
          type: array
          items:
            $ref: '#/components/schemas/Rule'
        meta:
          $ref: '#/components/schemas/RulesResponseMetadata'
    Error:
      type: object
      required:
        - code
        - message
      properties:
        code:
          type: integer
          format: int32
        message:
          type: string
    Problem:
      type: object
      description: >-
        An HTTP Problem Details object, as defined in IETF RFC 7807
        (https://tools.ietf.org/html/rfc7807).
      required:
        - type
        - title
      properties:
        detail:
          type: string
        status:
          type: integer
        title:
          type: string
        type:
          type: string
      discriminator:
        propertyName: type
        mapping:
          about:blank: '#/components/schemas/GenericProblem'
          https://api.twitter.com/2/problems/client-disconnected: '#/components/schemas/ClientDisconnectedProblem'
          https://api.twitter.com/2/problems/client-forbidden: '#/components/schemas/ClientForbiddenProblem'
          https://api.twitter.com/2/problems/conflict: '#/components/schemas/ConflictProblem'
          https://api.twitter.com/2/problems/disallowed-resource: '#/components/schemas/DisallowedResourceProblem'
          https://api.twitter.com/2/problems/duplicate-rules: '#/components/schemas/DuplicateRuleProblem'
          https://api.twitter.com/2/problems/invalid-request: '#/components/schemas/InvalidRequestProblem'
          https://api.twitter.com/2/problems/invalid-rules: '#/components/schemas/InvalidRuleProblem'
          https://api.twitter.com/2/problems/noncompliant-rules: '#/components/schemas/NonCompliantRulesProblem'
          https://api.twitter.com/2/problems/not-authorized-for-field: '#/components/schemas/FieldUnauthorizedProblem'
          https://api.twitter.com/2/problems/not-authorized-for-resource: '#/components/schemas/ResourceUnauthorizedProblem'
          https://api.twitter.com/2/problems/operational-disconnect: '#/components/schemas/OperationalDisconnectProblem'
          https://api.twitter.com/2/problems/resource-not-found: '#/components/schemas/ResourceNotFoundProblem'
          https://api.twitter.com/2/problems/resource-unavailable: '#/components/schemas/ResourceUnavailableProblem'
          https://api.twitter.com/2/problems/rule-cap: '#/components/schemas/RulesCapProblem'
          https://api.twitter.com/2/problems/streaming-connection: '#/components/schemas/ConnectionExceptionProblem'
          https://api.twitter.com/2/problems/unsupported-authentication: '#/components/schemas/UnsupportedAuthenticationProblem'
          https://api.twitter.com/2/problems/usage-capped: '#/components/schemas/UsageCapExceededProblem'
    Rule:
      type: object
      description: A user-provided stream filtering rule.
      required:
        - value
      properties:
        id:
          $ref: '#/components/schemas/RuleId'
        tag:
          $ref: '#/components/schemas/RuleTag'
        value:
          $ref: '#/components/schemas/RuleValue'
    RulesResponseMetadata:
      type: object
      required:
        - sent
      properties:
        next_token:
          $ref: '#/components/schemas/NextToken'
        result_count:
          type: integer
          description: Number of Rules in result set.
          format: int32
        sent:
          type: string
        summary:
          $ref: '#/components/schemas/RulesRequestSummary'
    RuleTag:
      type: string
      description: A tag meant for the labeling of user provided rules.
      example: Non-retweeted coffee Posts
    RuleValue:
      type: string
      description: The filterlang value of the rule.
      example: coffee -is:retweet
    NextToken:
      type: string
      description: The next token.
      minLength: 1
    RulesRequestSummary:
      oneOf:
        - type: object
          description: >-
            A summary of the results of the addition of user-specified stream
            filtering rules.
          required:
            - created
            - not_created
            - valid
            - invalid
          properties:
            created:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were
                created.
              format: int32
              example: 1
            invalid:
              type: integer
              description: Number of invalid user-specified stream filtering rules.
              format: int32
              example: 1
            not_created:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were not
                created.
              format: int32
              example: 1
            valid:
              type: integer
              description: Number of valid user-specified stream filtering rules.
              format: int32
              example: 1
        - type: object
          required:
            - deleted
            - not_deleted
          properties:
            deleted:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were
                deleted.
              format: int32
            not_deleted:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were not
                deleted.
              format: int32
  securitySchemes:
    BearerToken:
      type: http
      scheme: bearer

````
> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Update stream rules

> Adds or deletes rules from the active rule set for the filtered stream.



## OpenAPI

````yaml post /2/tweets/search/stream/rules
openapi: 3.0.0
info:
  description: X API v2 available endpoints
  version: '2.157'
  title: X API v2
  termsOfService: https://developer.x.com/en/developer-terms/agreement-and-policy.html
  contact:
    name: X Developers
    url: https://developer.x.com/
  license:
    name: X Developer Agreement and Policy
    url: https://developer.x.com/en/developer-terms/agreement-and-policy.html
servers:
  - description: X API
    url: https://api.x.com
security: []
tags:
  - name: Account Activity
    description: Endpoints relating to retrieving, managing AAA subscriptions
    externalDocs:
      description: Find out more
      url: >-
        https://docs.x.com/x-api/enterprise-gnip-2.0/fundamentals/account-activity
  - name: Bookmarks
    description: Endpoints related to retrieving, managing bookmarks of a user
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/bookmarks
  - name: Compliance
    description: Endpoints related to keeping X data in your systems compliant
    externalDocs:
      description: Find out more
      url: >-
        https://developer.twitter.com/en/docs/twitter-api/compliance/batch-tweet/introduction
  - name: Connections
    description: Endpoints related to streaming connections
    externalDocs:
      description: Find out more
      url: https://developer.x.com/en/docs/x-api/connections
  - name: Direct Messages
    description: Endpoints related to retrieving, managing Direct Messages
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/direct-messages
  - name: General
    description: Miscellaneous endpoints for general API functionality
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api
  - name: Lists
    description: Endpoints related to retrieving, managing Lists
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/lists
  - name: Media
    description: Endpoints related to Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: MediaUpload
    description: Endpoints related to uploading Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: News
    description: Endpoint for retrieving news stories
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/news
  - name: Spaces
    description: Endpoints related to retrieving, managing Spaces
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/spaces
  - name: Stream
    description: Endpoints related to streaming
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: Tweets
    description: Endpoints related to retrieving, searching, and modifying Tweets
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/tweets/lookup
  - name: Users
    description: Endpoints related to retrieving, managing relationships of Users
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/users/lookup
paths:
  /2/tweets/search/stream/rules:
    post:
      tags:
        - Stream
        - Tweets
      summary: Update stream rules
      description: Adds or deletes rules from the active rule set for the filtered stream.
      operationId: updateRules
      parameters:
        - name: dry_run
          in: query
          description: >-
            Dry Run can be used with both the add and delete action, with the
            expected result given, but without actually taking any action in the
            system (meaning the end state will always be as it was when the
            request was submitted). This is particularly useful to validate rule
            changes.
          required: false
          schema:
            type: boolean
          style: form
        - name: delete_all
          in: query
          description: >-
            Delete All can be used to delete all of the rules associated this
            client app, it should be specified with no other parameters. Once
            deleted, rules cannot be recovered.
          required: false
          schema:
            type: boolean
          style: form
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AddOrDeleteRulesRequest'
        required: true
      responses:
        '200':
          description: The request has succeeded.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AddOrDeleteRulesResponse'
        default:
          description: The request has failed.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
            application/problem+json:
              schema:
                $ref: '#/components/schemas/Problem'
      security:
        - BearerToken: []
      externalDocs:
        url: >-
          https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/api-reference/post-tweets-search-stream-rules
components:
  schemas:
    AddOrDeleteRulesRequest:
      oneOf:
        - $ref: '#/components/schemas/AddRulesRequest'
        - $ref: '#/components/schemas/DeleteRulesRequest'
    AddOrDeleteRulesResponse:
      type: object
      description: A response from modifying user-specified stream filtering rules.
      required:
        - meta
      properties:
        data:
          type: array
          description: All user-specified stream filtering rules that were created.
          items:
            $ref: '#/components/schemas/Rule'
        errors:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/Problem'
        meta:
          $ref: '#/components/schemas/RulesResponseMetadata'
    Error:
      type: object
      required:
        - code
        - message
      properties:
        code:
          type: integer
          format: int32
        message:
          type: string
    Problem:
      type: object
      description: >-
        An HTTP Problem Details object, as defined in IETF RFC 7807
        (https://tools.ietf.org/html/rfc7807).
      required:
        - type
        - title
      properties:
        detail:
          type: string
        status:
          type: integer
        title:
          type: string
        type:
          type: string
      discriminator:
        propertyName: type
        mapping:
          about:blank: '#/components/schemas/GenericProblem'
          https://api.twitter.com/2/problems/client-disconnected: '#/components/schemas/ClientDisconnectedProblem'
          https://api.twitter.com/2/problems/client-forbidden: '#/components/schemas/ClientForbiddenProblem'
          https://api.twitter.com/2/problems/conflict: '#/components/schemas/ConflictProblem'
          https://api.twitter.com/2/problems/disallowed-resource: '#/components/schemas/DisallowedResourceProblem'
          https://api.twitter.com/2/problems/duplicate-rules: '#/components/schemas/DuplicateRuleProblem'
          https://api.twitter.com/2/problems/invalid-request: '#/components/schemas/InvalidRequestProblem'
          https://api.twitter.com/2/problems/invalid-rules: '#/components/schemas/InvalidRuleProblem'
          https://api.twitter.com/2/problems/noncompliant-rules: '#/components/schemas/NonCompliantRulesProblem'
          https://api.twitter.com/2/problems/not-authorized-for-field: '#/components/schemas/FieldUnauthorizedProblem'
          https://api.twitter.com/2/problems/not-authorized-for-resource: '#/components/schemas/ResourceUnauthorizedProblem'
          https://api.twitter.com/2/problems/operational-disconnect: '#/components/schemas/OperationalDisconnectProblem'
          https://api.twitter.com/2/problems/resource-not-found: '#/components/schemas/ResourceNotFoundProblem'
          https://api.twitter.com/2/problems/resource-unavailable: '#/components/schemas/ResourceUnavailableProblem'
          https://api.twitter.com/2/problems/rule-cap: '#/components/schemas/RulesCapProblem'
          https://api.twitter.com/2/problems/streaming-connection: '#/components/schemas/ConnectionExceptionProblem'
          https://api.twitter.com/2/problems/unsupported-authentication: '#/components/schemas/UnsupportedAuthenticationProblem'
          https://api.twitter.com/2/problems/usage-capped: '#/components/schemas/UsageCapExceededProblem'
    AddRulesRequest:
      type: object
      description: A request to add a user-specified stream filtering rule.
      required:
        - add
      properties:
        add:
          type: array
          items:
            $ref: '#/components/schemas/RuleNoId'
    DeleteRulesRequest:
      type: object
      description: A response from deleting user-specified stream filtering rules.
      required:
        - delete
      properties:
        delete:
          type: object
          description: IDs and values of all deleted user-specified stream filtering rules.
          properties:
            ids:
              type: array
              description: IDs of all deleted user-specified stream filtering rules.
              items:
                $ref: '#/components/schemas/RuleId'
            values:
              type: array
              description: Values of all deleted user-specified stream filtering rules.
              items:
                $ref: '#/components/schemas/RuleValue'
    Rule:
      type: object
      description: A user-provided stream filtering rule.
      required:
        - value
      properties:
        id:
          $ref: '#/components/schemas/RuleId'
        tag:
          $ref: '#/components/schemas/RuleTag'
        value:
          $ref: '#/components/schemas/RuleValue'
    RulesResponseMetadata:
      type: object
      required:
        - sent
      properties:
        next_token:
          $ref: '#/components/schemas/NextToken'
        result_count:
          type: integer
          description: Number of Rules in result set.
          format: int32
        sent:
          type: string
        summary:
          $ref: '#/components/schemas/RulesRequestSummary'
    RuleNoId:
      type: object
      description: A user-provided stream filtering rule.
      required:
        - value
      properties:
        tag:
          $ref: '#/components/schemas/RuleTag'
        value:
          $ref: '#/components/schemas/RuleValue'
    RuleId:
      type: string
      description: Unique identifier of this rule.
      pattern: ^[0-9]{1,19}$
      example: '120897978112909812'
    RuleValue:
      type: string
      description: The filterlang value of the rule.
      example: coffee -is:retweet
    RuleTag:
      type: string
      description: A tag meant for the labeling of user provided rules.
      example: Non-retweeted coffee Posts
    NextToken:
      type: string
      description: The next token.
      minLength: 1
    RulesRequestSummary:
      oneOf:
        - type: object
          description: >-
            A summary of the results of the addition of user-specified stream
            filtering rules.
          required:
            - created
            - not_created
            - valid
            - invalid
          properties:
            created:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were
                created.
              format: int32
              example: 1
            invalid:
              type: integer
              description: Number of invalid user-specified stream filtering rules.
              format: int32
              example: 1
            not_created:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were not
                created.
              format: int32
              example: 1
            valid:
              type: integer
              description: Number of valid user-specified stream filtering rules.
              format: int32
              example: 1
        - type: object
          required:
            - deleted
            - not_deleted
          properties:
            deleted:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were
                deleted.
              format: int32
            not_deleted:
              type: integer
              description: >-
                Number of user-specified stream filtering rules that were not
                deleted.
              format: int32
  securitySchemes:
    BearerToken:
      type: http
      scheme: bearer

````
> ## Documentation Index
> Fetch the complete documentation index at: https://docs.x.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Get stream rule counts

> Retrieves the count of rules in the active rule set for the filtered stream.



## OpenAPI

````yaml get /2/tweets/search/stream/rules/counts
openapi: 3.0.0
info:
  description: X API v2 available endpoints
  version: '2.157'
  title: X API v2
  termsOfService: https://developer.x.com/en/developer-terms/agreement-and-policy.html
  contact:
    name: X Developers
    url: https://developer.x.com/
  license:
    name: X Developer Agreement and Policy
    url: https://developer.x.com/en/developer-terms/agreement-and-policy.html
servers:
  - description: X API
    url: https://api.x.com
security: []
tags:
  - name: Account Activity
    description: Endpoints relating to retrieving, managing AAA subscriptions
    externalDocs:
      description: Find out more
      url: >-
        https://docs.x.com/x-api/enterprise-gnip-2.0/fundamentals/account-activity
  - name: Bookmarks
    description: Endpoints related to retrieving, managing bookmarks of a user
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/bookmarks
  - name: Compliance
    description: Endpoints related to keeping X data in your systems compliant
    externalDocs:
      description: Find out more
      url: >-
        https://developer.twitter.com/en/docs/twitter-api/compliance/batch-tweet/introduction
  - name: Connections
    description: Endpoints related to streaming connections
    externalDocs:
      description: Find out more
      url: https://developer.x.com/en/docs/x-api/connections
  - name: Direct Messages
    description: Endpoints related to retrieving, managing Direct Messages
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/direct-messages
  - name: General
    description: Miscellaneous endpoints for general API functionality
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api
  - name: Lists
    description: Endpoints related to retrieving, managing Lists
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/lists
  - name: Media
    description: Endpoints related to Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: MediaUpload
    description: Endpoints related to uploading Media
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: News
    description: Endpoint for retrieving news stories
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/news
  - name: Spaces
    description: Endpoints related to retrieving, managing Spaces
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/spaces
  - name: Stream
    description: Endpoints related to streaming
    externalDocs:
      description: Find out more
      url: https://developer.x.com
  - name: Tweets
    description: Endpoints related to retrieving, searching, and modifying Tweets
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/tweets/lookup
  - name: Users
    description: Endpoints related to retrieving, managing relationships of Users
    externalDocs:
      description: Find out more
      url: https://developer.twitter.com/en/docs/twitter-api/users/lookup
paths:
  /2/tweets/search/stream/rules/counts:
    get:
      tags:
        - Stream
        - Tweets
      summary: Get stream rule counts
      description: >-
        Retrieves the count of rules in the active rule set for the filtered
        stream.
      operationId: getRuleCounts
      parameters:
        - $ref: '#/components/parameters/RulesCountFieldsParameter'
      responses:
        '200':
          description: The request has succeeded.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Get2TweetsSearchStreamRulesCountsResponse'
        default:
          description: The request has failed.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
            application/problem+json:
              schema:
                $ref: '#/components/schemas/Problem'
      security:
        - BearerToken: []
      externalDocs:
        url: >-
          https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/api-reference/get-tweets-search-stream-rules-counts
components:
  parameters:
    RulesCountFieldsParameter:
      name: rules_count.fields
      in: query
      description: A comma separated list of RulesCount fields to display.
      required: false
      schema:
        type: array
        description: The fields available for a RulesCount object.
        minItems: 1
        uniqueItems: true
        items:
          type: string
          enum:
            - all_project_client_apps
            - cap_per_client_app
            - cap_per_project
            - client_app_rules_count
            - project_rules_count
        example:
          - all_project_client_apps
          - cap_per_client_app
          - cap_per_project
          - client_app_rules_count
          - project_rules_count
      explode: false
      style: form
  schemas:
    Get2TweetsSearchStreamRulesCountsResponse:
      type: object
      properties:
        data:
          $ref: '#/components/schemas/RulesCount'
        errors:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/Problem'
    Error:
      type: object
      required:
        - code
        - message
      properties:
        code:
          type: integer
          format: int32
        message:
          type: string
    Problem:
      type: object
      description: >-
        An HTTP Problem Details object, as defined in IETF RFC 7807
        (https://tools.ietf.org/html/rfc7807).
      required:
        - type
        - title
      properties:
        detail:
          type: string
        status:
          type: integer
        title:
          type: string
        type:
          type: string
      discriminator:
        propertyName: type
        mapping:
          about:blank: '#/components/schemas/GenericProblem'
          https://api.twitter.com/2/problems/client-disconnected: '#/components/schemas/ClientDisconnectedProblem'
          https://api.twitter.com/2/problems/client-forbidden: '#/components/schemas/ClientForbiddenProblem'
          https://api.twitter.com/2/problems/conflict: '#/components/schemas/ConflictProblem'
          https://api.twitter.com/2/problems/disallowed-resource: '#/components/schemas/DisallowedResourceProblem'
          https://api.twitter.com/2/problems/duplicate-rules: '#/components/schemas/DuplicateRuleProblem'
          https://api.twitter.com/2/problems/invalid-request: '#/components/schemas/InvalidRequestProblem'
          https://api.twitter.com/2/problems/invalid-rules: '#/components/schemas/InvalidRuleProblem'
          https://api.twitter.com/2/problems/noncompliant-rules: '#/components/schemas/NonCompliantRulesProblem'
          https://api.twitter.com/2/problems/not-authorized-for-field: '#/components/schemas/FieldUnauthorizedProblem'
          https://api.twitter.com/2/problems/not-authorized-for-resource: '#/components/schemas/ResourceUnauthorizedProblem'
          https://api.twitter.com/2/problems/operational-disconnect: '#/components/schemas/OperationalDisconnectProblem'
          https://api.twitter.com/2/problems/resource-not-found: '#/components/schemas/ResourceNotFoundProblem'
          https://api.twitter.com/2/problems/resource-unavailable: '#/components/schemas/ResourceUnavailableProblem'
          https://api.twitter.com/2/problems/rule-cap: '#/components/schemas/RulesCapProblem'
          https://api.twitter.com/2/problems/streaming-connection: '#/components/schemas/ConnectionExceptionProblem'
          https://api.twitter.com/2/problems/unsupported-authentication: '#/components/schemas/UnsupportedAuthenticationProblem'
          https://api.twitter.com/2/problems/usage-capped: '#/components/schemas/UsageCapExceededProblem'
    RulesCount:
      type: object
      description: >-
        A count of user-provided stream filtering rules at the application and
        project levels.
      properties:
        all_project_client_apps:
          $ref: '#/components/schemas/AllProjectClientApps'
        cap_per_client_app:
          type: integer
          description: Cap of number of rules allowed per client application
          format: int32
        cap_per_project:
          type: integer
          description: Cap of number of rules allowed per project
          format: int32
        client_app_rules_count:
          $ref: '#/components/schemas/AppRulesCount'
        project_rules_count:
          type: integer
          description: Number of rules for project
          format: int32
    AllProjectClientApps:
      type: array
      description: Client App Rule Counts for all applications in the project
      items:
        $ref: '#/components/schemas/AppRulesCount'
    AppRulesCount:
      type: object
      description: >-
        A count of user-provided stream filtering rules at the client
        application level.
      properties:
        client_app_id:
          $ref: '#/components/schemas/ClientAppId'
        rule_count:
          type: integer
          description: Number of rules for client application
          format: int32
    ClientAppId:
      type: string
      description: The ID of the client application
      minLength: 1
      maxLength: 19
  securitySchemes:
    BearerToken:
      type: http
      scheme: bearer

````
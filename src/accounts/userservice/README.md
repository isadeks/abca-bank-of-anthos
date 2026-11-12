# User Service

The user service manages user accounts and authentication.
Credentials are owned by an [Amazon Cognito](https://aws.amazon.com/cognito/) user pool:
login authenticates against it and returns the **ID token Cognito issues**, which other
services use to authenticate users. The user service no longer signs tokens itself and no
longer stores password hashes (the `passhash` column is kept for the schema and holds an
empty value for users created after the migration).

Implemented in Python with Flask.

### Endpoints

| Endpoint            | Type  | Auth? | Description                                                      |
| ------------------- | ----- | ----- | ---------------------------------------------------------------- |
| `/login`            | GET   |       |  Authenticates against Cognito; returns `{"token": <ID token>}`. 401 for a wrong password, 404 for an unknown user. |
| `/ready`            | GET   |       |  Readiness probe endpoint.                                       |
| `/users`            | POST  |       |  Creates the Cognito user and stores the profile and generated account id in the accounts database. 409 if the username exists, 400 if the password violates the pool's password policy. |
| `/version`          | GET   |       |  Returns the contents of `$VERSION`                              |

### Environment Variables

- `VERSION`
  - a version string for the service
- `PORT`
  - the port for the webserver
- `COGNITO_USER_POOL_ID`
  - id of the Cognito user pool
- `COGNITO_APP_CLIENT_ID`
  - id of the pool's app client used for sign-in
- `COGNITO_REGION`
  - AWS region of the pool (falls back to `AWS_REGION`)
  - if any of the three is missing the service still starts (probes work) but logs a critical
    error and answers `/login` and `/users` with 500
- `LOG_LEVEL`
  - the service-specific [logging level](https://docs.python.org/3/library/logging.html#levels) (default: INFO)

- ConfigMap `environment-config`:
  - `LOCAL_ROUTING_NUM`
    - the routing number for our bank

- ConfigMap `accounts-db-config`:
  - `ACCOUNTS_DB_URI`
    - the complete URI for the `accounts-db` database

### Cognito set-up

- **User pool**: sign-in by username (case sensitive usernames, matching the accounts database).
  Define a custom attribute `acct` (String, mutable) and keep `name` as a standard attribute.
- **App client**: a public client (no client secret) with the `ALLOW_USER_PASSWORD_AUTH` flow
  enabled; its token validity sets how long a login lasts (this replaces `TOKEN_EXPIRY_SECONDS`).
  Disable `PreventUserExistenceErrors` for the client, otherwise an unknown user cannot be told
  apart from a wrong password (404 vs 401).
- **IAM**: login (`InitiateAuth`) is a public call; signup needs the pod's service account to be
  allowed `cognito-idp:AdminCreateUser`, `AdminSetUserPassword` and `AdminDeleteUser` on the pool.

### Token claim contract

`/login` returns the Cognito **ID token** unchanged (`token_use` = `id`, signed RS256 with the
pool's keys at
`https://cognito-idp.<region>.amazonaws.com/<pool id>/.well-known/jwks.json`). Consumers must
verify the signature, `iss` (`https://cognito-idp.<region>.amazonaws.com/<pool id>`), `aud` (the app
client id), `token_use` (`id`) and `exp`, and then read:

| Claim              | Meaning                                       | Replaces (old token) |
| ------------------ | --------------------------------------------- | -------------------- |
| `cognito:username` | the Bank of Anthos username                   | `user`               |
| `custom:acct`      | the 10 digit account id                       | `acct`               |
| `name`             | display name, `<first name> <last name>`      | `name`               |
| `sub`              | Cognito's stable user id (not used by the app) | –                    |

`custom:acct` and `name` are set when the user is created (signup, or the import below), from the
generated account id and the submitted first and last name. Cognito (not the user service) decides
the token's `iat` / `exp`.

### Importing the demo user

Cognito cannot import the bcrypt hashes of the accounts database, so existing users have to be
created in the pool with a password. For the demo user `testuser` (account id and name are read
from the accounts database, the password is the demo password `bankofanthos`), run once, from this
directory, with AWS credentials that can manage the pool:

```
export ACCOUNTS_DB_URI=<accounts-db uri> COGNITO_USER_POOL_ID=<pool id> \
       COGNITO_APP_CLIENT_ID=<client id> COGNITO_REGION=<region>
python tools/import_demo_user.py
```

`--username` and `--password` import another accounts-db user. It is safe to run again: a user that
is already in the pool is left as is.

### Kubernetes Resources

- [deployments/userservice](/kubernetes-manifests/userservice.yaml)
- [service/userservice](/kubernetes-manifests/userservice.yaml)

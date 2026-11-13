# User Service

The user service manages user accounts and authentication. 
It creates and signs JWTs that are used by other services to authenticate users.

Implemented in Python with Flask.

### Endpoints

| Endpoint            | Type  | Auth? | Description                                                      |
| ------------------- | ----- | ----- | ---------------------------------------------------------------- |
| `/login`            | GET   |       |  Returns a JWT if authentication is successful.                  |
| `/ready`            | GET   |       |  Readiness probe endpoint.                                       |
| `/users`            | POST  |       |  Validates and creates a new user record.                        |
| `/accounts/<user>`  | GET   | JWT   |  Lists the user's accounts (the sign-up "Checking" account first). |
| `/accounts/<user>`  | POST  | JWT   |  Opens an additional account (`label`, at most 5 accounts per user). |
| `/accounts/<user>/token` | POST | JWT |  Returns a JWT acting on another of the user's accounts (`accountid`); it expires with the presented one. |
| `/version`          | GET   |       |  Returns the contents of `$VERSION`                              |

A user's account number is the `acct` claim of the JWT, so the ledger services
act on whichever account the token names. The account created at sign-up is in the
`users` table; additional accounts are rows of the `accounts` table (created at
startup if the database predates it).

### Environment Variables

- `VERSION`
  - a version string for the service
- `PORT`
  - the port for the webserver
- `PRIV_KEY_PATH`
  - the path to the private key for JWT signing, mounted as a secret
- `TOKEN_EXPIRY_SECONDS`
  - how long JWTs are valid before forcing user logout
- `LOG_LEVEL`
  - the service-specific [logging level](https://docs.python.org/3/library/logging.html#levels) (default: INFO)

- ConfigMap `environment-config`:
  - `LOCAL_ROUTING_NUM`
    - the routing number for our bank
  - `PUB_KEY_PATH`
    - the path to the JWT signer's public key, mounted as a secret

- ConfigMap `accounts-db-config`:
  - `ACCOUNTS_DB_URI`
    - the complete URI for the `accounts-db` database

### Kubernetes Resources

- [deployments/userservice](/kubernetes-manifests/userservice.yaml)
- [service/userservice](/kubernetes-manifests/userservice.yaml)

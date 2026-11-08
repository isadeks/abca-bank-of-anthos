# Budgets Service

The budgets service stores one monthly spending limit per user, so that a budget
survives restarts. The frontend uses it to show how much of the limit has been
used and to warn before a payment that would exceed it.

Implemented in Python with Flask.

### Endpoints

| Endpoint             | Type   | Auth? | Description                                                              |
| -------------------- | ------ | ----- | ------------------------------------------------------------------------ |
| `/budget/<username>` | GET    | 🔒    | Read the monthly limit of the authenticated user.                        |
| `/budget/<username>` | PUT    | 🔒    | Set (create or update) the monthly limit of the authenticated user.      |
| `/budget/<username>` | DELETE | 🔒    | Clear the monthly limit of the authenticated user.                       |
| `/ready`             | GET    |       | Readiness probe endpoint.                                                |
| `/version`           | GET    |       | Returns the contents of `$VERSION`                                       |

Every call to `/budget/<username>` needs the login token in the `Authorization`
header (`Bearer <jwt>` or the bare token, as for the contacts service), and
`<username>` must be the user the token was issued to. Otherwise the service
answers `401 authentication denied`.

The limit is an integer number of **whole cents** (`$500.00` is `50000`).

#### `GET /budget/<username>`

- `200` `{"limit_cents": 50000}`
- `200` `{"limit_cents": null}` when the user has no budget
- `401` authentication denied, `500` database error

#### `PUT /budget/<username>`

Request body (JSON): `{"limit_cents": 50000}`. `limit_cents` must be an integer
from `1` to `100000000000`; use `DELETE` to remove a budget.

- `200` `{"limit_cents": 50000}`: the stored limit (created or replaced)
- `400` missing or invalid `limit_cents`
- `401` authentication denied, `500` database error

#### `DELETE /budget/<username>`

- `204` no content: the budget is cleared (also when none was set)
- `401` authentication denied, `500` database error

### Storage

The limit lives in the `budgets` table of the `accounts-db` database
(`username` primary key, a foreign key to `users`, and `limit_cents BIGINT`).
The database initialisation scripts only run on a fresh database, so the service
runs `CREATE TABLE IF NOT EXISTS budgets ...` on startup.

### Environment Variables

- `VERSION`
  - a version string for the service
- `PORT`
  - the port for the webserver
- `LOG_LEVEL`
  - the service-wide [logging level](https://docs.python.org/3/library/logging.html#levels) (default: INFO)
- `ENABLE_TRACING`
  - `true` to export traces over OTLP (configured with the standard `OTEL_*` variables)

- ConfigMap `environment-config`:
  - `PUB_KEY_PATH`
    - the path to the JWT signer's public key, mounted as a secret

- ConfigMap `accounts-db-config`:
  - `ACCOUNTS_DB_URI`
    - the complete URI for the `accounts-db` database

- ConfigMap `service-api-config`:
  - `BUDGETS_API_ADDR` (`budgets:8080`) is the address other services call this service on

### Kubernetes Resources

- [deployments/budgets](/kubernetes-manifests/budgets.yaml)
- [service/budgets](/kubernetes-manifests/budgets.yaml)

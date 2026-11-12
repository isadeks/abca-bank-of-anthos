/*
 * Copyright 2020, Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

CREATE TABLE IF NOT EXISTS users (
  accountid CHAR(10) PRIMARY KEY,
  username VARCHAR(64) UNIQUE NOT NULL,
  passhash BYTEA NOT NULL,
  firstname VARCHAR(64) NOT NULL,
  lastname VARCHAR(64) NOT NULL,
  birthday DATE NOT NULL,
  timezone VARCHAR(8) NOT NULL,
  address VARCHAR(64) NOT NULL,
  state CHAR(2) NOT NULL,
  zip VARCHAR(5) NOT NULL,
  ssn CHAR(11) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_accountid ON users (accountid);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);



CREATE TABLE IF NOT EXISTS contacts (
  username VARCHAR(64) NOT NULL,
  label VARCHAR(128) NOT NULL,
  account_num CHAR(10) NOT NULL,
  routing_num CHAR(9) NOT NULL,
  is_external BOOLEAN NOT NULL,
  FOREIGN KEY (username) REFERENCES users(username)
);

CREATE INDEX IF NOT EXISTS idx_contacts_username ON contacts (username);



-- Recurring payments of the scheduledpayments service. The service creates
-- these tables itself if they are missing (databases made before they existed).
CREATE TABLE IF NOT EXISTS scheduled_payments (
  schedule_id VARCHAR(36) PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  from_account_num VARCHAR(10) NOT NULL,
  to_account_num VARCHAR(10) NOT NULL,
  to_label VARCHAR(128) NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  frequency VARCHAR(7) NOT NULL CHECK (frequency IN ('weekly', 'monthly')),
  anchor_day INTEGER NOT NULL CHECK (anchor_day BETWEEN 1 AND 31),
  next_payment_date DATE NOT NULL,
  status VARCHAR(9) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
  last_status VARCHAR(9),
  last_error TEXT,
  last_attempt_date DATE,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (username) REFERENCES users(username)
);

CREATE INDEX IF NOT EXISTS idx_scheduled_payments_username ON scheduled_payments (username);
CREATE INDEX IF NOT EXISTS idx_scheduled_payments_due ON scheduled_payments (status, next_payment_date);

-- One row per (schedule, due date): the primary key is what stops a due date
-- from being paid twice.
CREATE TABLE IF NOT EXISTS scheduled_payment_attempts (
  schedule_id VARCHAR(36) NOT NULL REFERENCES scheduled_payments(schedule_id),
  due_date DATE NOT NULL,
  status VARCHAR(9) NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed')),
  error TEXT,
  claimed_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (schedule_id, due_date)
);

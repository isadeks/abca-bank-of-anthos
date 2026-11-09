// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "$1,234.50" for 123450 cents, "-$3.00" for -300, "$---" when there is no amount. */
export function formatCurrency(cents) {
  if (cents === null || cents === undefined) {
    return '$---';
  }
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100).toLocaleString('en-US');
  const rest = String(abs % 100).padStart(2, '0');
  return `${cents < 0 ? '-' : ''}$${dollars}.${rest}`;
}

/**
 * "Oct 05" for a timestamp such as "2020-10-05T18:13:52.000+0000". The date
 * is the one written in the timestamp, whatever the viewer's time zone.
 */
export function formatDate(timestamp) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(timestamp ?? '');
  if (!match) {
    return '';
  }
  return `${MONTHS[Number(match[2]) - 1]} ${match[3]}`;
}

/** A random (version 4) UUID, which identifies a transaction to the ledger. */
export function uuidv4() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

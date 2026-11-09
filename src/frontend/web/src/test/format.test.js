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

import { describe, expect, it } from 'vitest';
import { formatCurrency, formatDate, uuidv4 } from '../format.js';

describe('formatCurrency', () => {
  it('formats cents as dollars', () => {
    expect(formatCurrency(123456)).toBe('$1,234.56');
    expect(formatCurrency(5)).toBe('$0.05');
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('keeps the sign of negative amounts', () => {
    expect(formatCurrency(-250)).toBe('-$2.50');
  });

  it('shows placeholders for a missing amount', () => {
    expect(formatCurrency(null)).toBe('$---');
    expect(formatCurrency(undefined)).toBe('$---');
  });
});

describe('formatDate', () => {
  it('shows the month and the day of a timestamp', () => {
    expect(formatDate('2021-03-07T12:30:00.000+0000')).toBe('Mar 07');
  });

  it('is empty for something that is not a timestamp', () => {
    expect(formatDate(undefined)).toBe('');
    expect(formatDate('yesterday')).toBe('');
  });
});

describe('uuidv4', () => {
  it('makes version 4 identifiers that differ', () => {
    const first = uuidv4();
    expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(uuidv4()).not.toBe(first);
  });
});

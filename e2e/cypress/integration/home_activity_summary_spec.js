/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

const defaultUser = Cypress.env('defaultUser')

describe('Home page activity summary', function () {
    beforeEach(function () {
        cy.loginRequest(defaultUser.username, defaultUser.password)
        cy.visit('/home')
    })

    it('shows money in and money out totals', function () {
        cy.get('#activity-summary').should('be.visible')
        cy.get('#summary-money-in').contains('$')
        cy.get('#summary-money-out').contains('$')
    })

    it('marks transactions as credit or debit', function () {
        cy.get('#transaction-table .type-badge').should('have.length.greaterThan', 0)
        cy.get('#transaction-table .type-badge-credit').first().contains('Credit')
        cy.get('#transaction-table .type-badge-debit').first().contains('Debit')
    })
})

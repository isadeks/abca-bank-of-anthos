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
const username = defaultUser.username
const password = defaultUser.password
const externalAccount = defaultUser.externalAccounts[0]
const [alice, bob, eve] = defaultUser.recipients

describe('Split a bill', function () {
    before(function () {
        // make sure there is money in the account
        cy.loginRequest(username, password)
        cy.visit('/home')
        cy.deposit(externalAccount, 10000)
    })

    beforeEach(function () {
        cy.loginRequest(username, password)
        cy.visit('/home')
    })

    it('sees the split a bill button and opens its modal', function () {
        cy.get('#splitSpan').contains('Split a Bill')
        cy.get('#splitBill').should('not.be.visible')
        cy.get('#splitSpan').click()
        cy.get('#splitBill').should('be.visible')
    })

    it('needs 2 to 4 contacts', function () {
        cy.get('#splitSpan').click()
        cy.get(`input.split-contact[value="${alice.accountNum}"]`).check({ force: true })
        cy.get('#split-amount').type('10.00')
        cy.get('#split-review').click()
        cy.get('#split-error').should('be.visible').contains('Pick 2 to 4 contacts')
    })

    it('shows a summary with the last share absorbing the rounding, then sends it', function () {
        cy.get('#splitSpan').click()
        ;[alice, bob, eve].forEach((contact) => {
            cy.get(`input.split-contact[value="${contact.accountNum}"]`).check({ force: true })
        })
        cy.get('#split-amount').type('10.01')
        cy.get('#split-review').click()

        cy.get('#split-summary-rows tr').should('have.length', 3)
        cy.get('#split-summary-rows tr').eq(0).contains('$3.33')
        cy.get('#split-summary-rows tr').eq(1).contains('$3.33')
        cy.get('#split-summary-rows tr').eq(2).contains('$3.35')
        cy.get('#split-summary-total').contains('$10.01')

        cy.get('#split-send').click()
        cy.get('#alert-message').contains('Bill split between 3 contacts')
    })
})

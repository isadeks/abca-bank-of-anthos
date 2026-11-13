/**
 * Copyright 2020 Google LLC
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

describe('User can have multiple accounts', function () {
    const uuid = () => Cypress._.random(0, 1e6)
    const password = 'bells'

    beforeEach(function () {
        const id = uuid()
        cy.createAccount({
            username: `multi_${id}`,
            firstName: 'Tom',
            lastName: `Nook-${id}`,
            password: password,
        })
        cy.url().should('include', '/home')
    })

    const openAccount = (label) => {
        cy.get('#accountSwitcherDropdown').click()
        cy.get('#open-account-link').click()
        cy.get('#openAccount').should('be.visible')
        cy.get('#new-account-label').type(label)
        cy.get('#open-account-form button[type=submit]').click()
    }

    it('shows only the sign-up account at first', function () {
        cy.get('#account-title').contains('Checking Account')
        cy.get('#active-account-label').contains('Checking')
        cy.get('.account-switch-option').should('have.length', 1)
        cy.get('#transfer-form').should('not.exist')
    })

    it('opens a second account with its own number and balance and switches to it', function () {
        cy.get('.account-number').invoke('text').then((checkingNumber) => {
            openAccount('Savings')
            cy.get('#alert-message', { timeout: 20000 }).contains('Opened account Savings')
            cy.get('#account-title').contains('Savings Account')
            cy.get('.account-number').invoke('text').should('not.eq', checkingNumber)
            cy.get('#current-balance').contains('$0.00')

            // switch back through the header
            cy.get('#accountSwitcherDropdown').click()
            cy.get('.account-switch-option').should('have.length', 2)
            cy.get('.account-switch-option').contains('Checking').click()
            cy.get('#account-title').contains('Checking Account')
            cy.get('.account-number').invoke('text').should('eq', checkingNumber)
        })
    })

    it('transfers between own accounts', function () {
        // a new user has no saved external accounts: deposit from a new one
        cy.get('#depositSpan').click()
        cy.get('#depositFunds').should('be.visible')
        cy.get('#accounts').select('add')
        cy.get('#external_account_num').type('1234567890')
        cy.get('#external_routing_num').type('123456789')
        cy.get('#deposit-amount').clear().type('100')
        cy.get('#deposit-form button[type=submit]').click()
        cy.get('#alert-message', { timeout: 20000 }).contains('Deposit successful')
        openAccount('Savings')
        cy.get('#account-title').contains('Savings Account')

        cy.get('#accountSwitcherDropdown').click()
        cy.get('.account-switch-option').contains('Checking').click()
        cy.get('#account-title').contains('Checking Account')
        cy.get('#current-balance').contains('$100.00')

        cy.get('#transferSpan').click()
        cy.get('#transferFunds').should('be.visible')
        cy.get('#transfer-to option').first().invoke('val').then((target) => {
            cy.get('#transfer-to').select(target)
        })
        cy.get('#transfer-amount').clear().type('30')
        cy.get('#transfer-form button[type=submit]').click()
        cy.get('#alert-message', { timeout: 20000 }).contains('Transfer successful')
        cy.get('#current-balance').contains('$70.00')

        cy.get('#accountSwitcherDropdown').click()
        cy.get('.account-switch-option').contains('Savings').click()
        cy.get('#current-balance').contains('$30.00')
    })
})

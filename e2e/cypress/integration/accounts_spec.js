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

    // Fund the signed-in user's account through the deposit endpoint (as the
    // deposit form does), then wait until the ledger reports the new balance.
    const fund = (amount) => {
        cy.request({
            method: 'POST',
            url: '/deposit',
            form: true,
            body: {
                account: 'add',
                external_account_num: '1234567890',
                external_routing_num: '123456789',
                amount: amount,
                uuid: `multi-${Date.now()}-${uuid()}`,
            },
        }).then((response) => {
            expect(response.status).to.eq(200)
            expect(response.body).to.contain('Deposit successful')
        })
    }

    const waitForBalance = (expected, attemptsLeft = 20) => {
        cy.request('/home').then((response) => {
            if (response.body.includes(expected)) {
                return
            }
            expect(attemptsLeft, `balance never reached ${expected}`).to.be.greaterThan(0)
            cy.wait(1000)
            waitForBalance(expected, attemptsLeft - 1)
        })
    }

    it('transfers between own accounts', function () {
        fund('100')
        waitForBalance('$100.00')

        openAccount('Savings')
        cy.get('#alert-message', { timeout: 20000 }).should('contain', 'Opened account Savings')
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
        cy.get('#transfer-form').submit()
        cy.get('#alert-message', { timeout: 20000 }).should('contain', 'Transfer successful')
        waitForBalance('$70.00')

        cy.reload()
        cy.get('#current-balance').contains('$70.00')
        cy.get('#accountSwitcherDropdown').click()
        cy.get('.account-switch-option').contains('Savings').click()
        cy.get('#account-title').contains('Savings Account')
        cy.get('#current-balance').contains('$30.00')
    })
})

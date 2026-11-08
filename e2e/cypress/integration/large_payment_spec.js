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
const recipient = defaultUser.recipients[0]
const transferMsgs = Cypress.env('messages').transfer

describe('Large payments are confirmed before they are sent', function () {
    before(function () {
        // make sure there is enough money in the account
        cy.loginRequest(defaultUser.username, defaultUser.password)
        cy.visit('/home')
        cy.deposit(defaultUser.externalAccounts[0], 10000)
    })
    beforeEach(function () {
        cy.loginRequest(defaultUser.username, defaultUser.password)
        cy.visit('/home')
    })

    it('asks for confirmation above $1,000 and sends once confirmed', function () {
        cy.transfer(recipient, 1500)
        cy.get('#payment-confirm').should('be.visible')
        cy.get('#payment-confirm-message').contains('You are about to send $1,500.00 to')
        cy.get('#payment-confirm-message').contains(recipient.accountNum)
        cy.get('#alert-message').should('not.exist')

        cy.get('#payment-confirm-send').click()
        cy.get('#alert-message').contains(transferMsgs.success)
    })

    it('can go back from the confirmation to change the payment', function () {
        cy.transfer(recipient, 1500)
        cy.get('#payment-confirm').should('be.visible')
        cy.get('#payment-confirm-back').click()
        cy.get('#payment-confirm').should('not.be.visible')
        cy.get('#payment-amount').should('be.visible')
    })

    it('does not ask for confirmation for $1,000 or less', function () {
        cy.transfer(recipient, 1000)
        cy.get('#alert-message').contains(transferMsgs.success)
    })
})

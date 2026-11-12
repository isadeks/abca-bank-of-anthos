/*
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
const recipient = defaultUser.recipients[0]

describe('Scheduled payments', function () {
    beforeEach(function () {
        cy.loginRequest(username, password)
        cy.visit('/home')
    })

    it('shows the schedule form and list', function () {
        cy.get('#schedule-form').should('be.visible')
        cy.get('#scheduled-payments').should('exist')
    })

    it('creates a weekly schedule, lists it and cancels it', function () {
        // a unique amount identifies the row even if earlier runs left schedules behind
        const cents = 100 + (Date.now() % 800)
        const amount = (cents / 100).toFixed(2)

        cy.get('#schedule-account').select(recipient.accountNum)
        cy.get('#schedule-amount').type(amount)
        cy.get('#schedule-frequency').select('weekly')
        cy.get('#schedule-submit').click()

        cy.get('#alert-message').should('contain', 'Scheduled payment created')
        cy.contains('#scheduled-payments tr.schedule-row', `$${amount}`).as('row')
        cy.get('@row').should('contain', recipient.name)
        cy.get('@row').find('.schedule-frequency').should('have.text', 'Weekly')
        cy.get('@row').find('.schedule-next-date').invoke('text').should('match', /^[A-Z][a-z]{2} \d{2}, \d{4}$/)

        cy.get('@row').find('.schedule-cancel').click()
        cy.get('#alert-message').should('contain', 'Scheduled payment cancelled')
        cy.get('#scheduled-payments').should('not.contain', `$${amount}`)
    })

    it('rejects a zero amount in the form', function () {
        cy.get('#schedule-amount').type('0')
        cy.get('#schedule-submit').click()
        cy.get('#schedule-form').should('have.class', 'was-validated')
        cy.url().should('include', '/home')
    })
})

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

describe('User can open a savings account', function() {
    const uuid = () => Cypress._.random(0, 1e6)

    beforeEach(function() {
        const id = uuid()
        cy.createAccount({
            username: `sav_${id}`,
            firstName: 'Tom',
            lastName: `Nook-${id}`,
            password: 'bells'
        })
    })

    it('is offered the option, then sees the new account number', function() {
        cy.get('#savings-account').contains("You don't have a savings account yet")
        cy.get('#open-savings-button').click()
        cy.get('#alert-message').contains('Savings account opened')
        cy.get('#savings-account-number').invoke('text').should('match', /^\d{10}$/)
        cy.get('#open-savings-button').should('not.exist')
    })
})

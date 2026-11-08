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

describe('Account number on the home page', function () {
    beforeEach(function () {
        cy.loginRequest(defaultUser.username, defaultUser.password)
        cy.visit('/home')
    })

    it('shows the account number with a Copy button', function () {
        cy.get('#account-number').invoke('text').should('match', /^\d{10}$/)
        cy.get('#copy-account-number').should('have.text', 'Copy')
            .and('have.attr', 'data-account-number')
            .and('match', /^\d{10}$/)
    })
})

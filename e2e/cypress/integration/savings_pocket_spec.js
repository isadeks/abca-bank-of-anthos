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


// A new customer's Savings pocket is empty: the home page shows the pocket
// card next to the main balance, and the move-back action is disabled.
describe('Savings pocket of a new customer', function() {
    beforeEach(function() {
        const user = {
            username: 'pocket' + Math.floor(Math.random() * 1000000),
            firstName: 'Pocket',
            lastName: 'Saver',
            password: 'bells'
        }
        cy.createAccount(user)
        cy.url().should('include', '/home')
    })

    it('shows the pocket card with a zero balance', function() {
        cy.get('#current-balance').should('be.visible')
        cy.get('#pocket-card').should('be.visible').and('contain', 'Savings Pocket')
        cy.get('#pocket-balance').should('contain', '$0.00')
    })

    it('disables the move to main account action', function() {
        cy.get('#pocket-move-button').should('contain', 'Move to main account')
        cy.get('#pocket-move-button').should('be.disabled')
    })
})

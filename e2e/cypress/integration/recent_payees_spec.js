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

describe('Recent payees and accounts quick picks', function () {
    beforeEach(function () {
        cy.loginRequest(defaultUser.username, defaultUser.password)
        cy.visit('/home')
    })

    it('shows at most 3 recent payees on the payment form and fills the recipient on click', function () {
        cy.get('#paymentSpan').click()
        cy.get('#recent-payees .recent-chip').should('have.length.within', 1, 3)
        cy.get('#recent-payees .recent-chip').first().then(($chip) => {
            const accountNum = $chip.attr('data-account-num')
            cy.wrap($chip).click()
            cy.get('#payment-accounts').find('option:selected').invoke('val').then((val) => {
                if (val === 'add') {
                    cy.get('#contact_account_num').should('have.value', accountNum)
                } else {
                    expect(val).to.equal(accountNum)
                }
            })
        })
    })

    it('shows at most 3 recent accounts on the deposit form and fills the account on click', function () {
        cy.get('#depositSpan').click()
        cy.get('#recent-depositors .recent-chip').should('have.length.within', 1, 3)
        cy.get('#recent-depositors .recent-chip').first().then(($chip) => {
            const accountNum = $chip.attr('data-account-num')
            cy.wrap($chip).click()
            cy.get('#accounts').find('option:selected').invoke('val').then((val) => {
                if (val === 'add') {
                    cy.get('#external_account_num').should('have.value', accountNum)
                } else {
                    expect(JSON.parse(val).account_num).to.equal(accountNum)
                }
            })
        })
    })
})

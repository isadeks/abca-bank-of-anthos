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

const defaultUser = Cypress.env('defaultUser')

describe('Security page', function() {
  it('requires a signed-in user', function() {
    cy.visit('/security')
    cy.url().should('include', '/login')
  })

  it('shows the two-factor setup QR code and secret, without turning it on', function() {
    cy.login(defaultUser.username, defaultUser.password)
    cy.visit('/security')
    cy.get('#twofa-status').should('contain', 'off')
    cy.get('#setup-submit').click()
    cy.get('#totp-qr svg').should('be.visible')
    cy.get('#totp-secret').invoke('text').should('match', /^[A-Z2-7]{16,}$/)
    cy.get('#enable-form').should('be.visible')
    // Cancelling leaves two-factor sign-in off, so other specs can still sign in
    cy.contains('a', 'Cancel').click()
    cy.get('#twofa-status').should('contain', 'off')
  })
})

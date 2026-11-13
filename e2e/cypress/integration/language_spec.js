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

describe('French language', function() {
  it('shows the login page in French and keeps English as the default', function() {
    cy.visit('/login')
    cy.get('html').should('have.attr', 'lang', 'en')
    cy.get('#create-account-btn').contains('Create an Account')
    cy.get('#lang-fr').click()
    cy.get('html').should('have.attr', 'lang', 'fr')
    cy.get('#create-account-btn').contains('Créer un compte')
    cy.get('#lang-en').click()
    cy.get('#create-account-btn').contains('Create an Account')
  })

  it('shows the home page in French after signing in', function() {
    cy.visit('/login?lang=fr')
    cy.get('#login-username').clear().type(defaultUser.username)
    cy.get('#login-password').clear().type(defaultUser.password)
    cy.get('#login-form').submit()
    cy.url().should('include', '/home')
    cy.get('html').should('have.attr', 'lang', 'fr')
    cy.get('#depositSpan').contains('Déposer des fonds')
    cy.get('#paymentSpan').contains('Envoyer un paiement')
    cy.get('#current-balance').contains('$')
  })
})

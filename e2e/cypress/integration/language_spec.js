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
const username = defaultUser.username
const password = defaultUser.password

describe('Language switch on the login page', function() {
  it('shows English by default', function() {
    cy.visit('/login')
    cy.get('#lang-en').should('have.class', 'active')
    cy.get('#login-form').contains('Sign in')
  })

  it('translates the page to Spanish and back', function() {
    cy.visit('/login')
    cy.get('#lang-es').click()
    cy.url().should('include', '/login')
    cy.get('#lang-es').should('have.class', 'active')
    cy.get('#login-form').contains('Iniciar sesión')
    cy.get('#lang-en').click()
    cy.get('#login-form').contains('Sign in')
  })
})

describe('Language switch on the home page', function() {
  beforeEach(function() {
    cy.login(username, password)
  })

  it('translates the home page, deposit and payment forms', function() {
    cy.get('#lang-es').click()
    cy.url().should('include', '/home')
    cy.get('.current-balance').contains('Saldo actual')
    cy.get('#depositSpan').contains('Depositar fondos')
    cy.get('#paymentSpan').contains('Enviar pago')
    cy.get('#depositSpan').click()
    cy.get('#deposit-form').contains('Hacer un depósito')
    cy.get('#deposit-form').contains('Importe del depósito')
    cy.get('#deposit-form .deposit-cancel').click()
    cy.get('#paymentSpan').click()
    cy.get('#payment-form').contains('Enviar un pago')
    cy.get('#payment-form').contains('Destinatario')
  })
})

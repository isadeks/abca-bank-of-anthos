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

describe('Login form accessibility', function() {
  it('labels its inputs', function() {
    cy.visit('/login')
    cy.get('label[for="login-username"]').should('exist')
    cy.get('label[for="login-password"]').should('exist')
  })

  it('announces a failed login through a role=alert region', function() {
    cy.visit('/login?msg=Login+Failed')
    cy.get('#login-alert-region[role="alert"]').should('exist')
    cy.get('#alertBanner').should('be.visible').contains('Login failed.')
  })
})

describe('Deposit and payment dialog accessibility', function() {
  beforeEach(function() {
    cy.login(defaultUser.username, defaultUser.password)
  })

  it('names the dialogs and labels every input', function() {
    cy.get('#depositFunds').should('have.attr', 'role', 'dialog')
      .and('have.attr', 'aria-labelledby', 'deposit-modal-title')
    cy.get('#sendPayment').should('have.attr', 'role', 'dialog')
      .and('have.attr', 'aria-labelledby', 'payment-modal-title')
    cy.get('#deposit-form input[type!="hidden"], #deposit-form select').each(($el) => {
      cy.get(`label[for="${$el.attr('id')}"]`).should('exist')
    })
    cy.get('#payment-form input[type!="hidden"], #payment-form select').each(($el) => {
      cy.get(`label[for="${$el.attr('id')}"]`).should('exist')
    })
  })

  it('marks an invalid amount and links it to its message', function() {
    cy.get('#depositSpan').click()
    cy.get('#deposit-amount').type('0')
    cy.get('#deposit-form button[type=submit]').click()
    cy.get('#deposit-amount').should('have.attr', 'aria-invalid', 'true')
    cy.get('#deposit-amount').invoke('attr', 'aria-describedby').then((id) => {
      cy.get(`#${id}`).should('be.visible').contains('valid amount')
    })
  })

  it('announces a failed payment message as an alert', function() {
    cy.visit('/home?msg=Payment+failed')
    cy.get('#alert-message-div').should('have.attr', 'role', 'alert')
  })
})

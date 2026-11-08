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

describe('Dark mode', function() {
  it('toggles the theme and remembers the choice in a cookie', function() {
    cy.login(defaultUser.username, defaultUser.password)
    cy.get('html').should('have.attr', 'data-theme', 'light')

    cy.get('#theme-toggle').click()
    cy.get('html').should('have.attr', 'data-theme', 'dark')
    cy.getCookie('theme').should('have.property', 'value', 'dark')

    // the choice survives a page load
    cy.reload()
    cy.get('html').should('have.attr', 'data-theme', 'dark')

    cy.get('#theme-toggle').click()
    cy.get('html').should('have.attr', 'data-theme', 'light')
    cy.getCookie('theme').should('have.property', 'value', 'light')
  })
})

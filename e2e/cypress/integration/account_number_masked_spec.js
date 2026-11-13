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

describe('Account number on the home page', function() {
  it('is masked to the last 4 digits with the full number in a tooltip', function() {
    const defaultUser = Cypress.env('defaultUser')
    cy.login(defaultUser.username, defaultUser.password)
    cy.url().should('include', '/home')
    cy.get('#account-number').should('contain', '••••')
      .invoke('attr', 'title').should('match', /^\d{10}$/)
    cy.get('#account-number').then(($el) => {
      const full = $el.attr('title')
      expect($el.text()).to.not.contain(full)
      expect($el.text()).to.contain(full.slice(-4))
    })
  })
})

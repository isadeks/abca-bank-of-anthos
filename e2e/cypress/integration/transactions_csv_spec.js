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

describe('Transaction history CSV export', function () {
    it('redirects to login when not authenticated', function () {
        cy.request({ url: '/transactions.csv', followRedirect: false })
            .its('status').should('eq', 302)
    })

    it('downloads the logged-in user transactions as CSV', function () {
        cy.login(defaultUser.username, defaultUser.password)
        cy.get('#download-csv').should('be.visible').and('contain', 'Download CSV')
        cy.request('/transactions.csv').then((resp) => {
            expect(resp.status).to.eq(200)
            expect(resp.headers['content-type']).to.contain('text/csv')
            expect(resp.headers['content-disposition']).to.contain('attachment')
            const lines = resp.body.trim().split(/\r?\n/)
            expect(lines[0]).to.eq('Date,Description,Amount,Type')
            expect(lines.length).to.be.greaterThan(1)
            expect(lines[1]).to.match(/^\d{4}-\d{2}-\d{2},.*,-?\d+\.\d{2},(Credit|Debit)$/)
        })
    })
})

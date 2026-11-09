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
const externalAccount = defaultUser.externalAccounts[0]

describe('Deposit amounts with too many decimals', function () {
    beforeEach(function () {
        cy.loginRequest(defaultUser.username, defaultUser.password)
    })

    const postDeposit = (amount) => cy.request({
        method: 'POST',
        url: '/deposit',
        form: true,
        failOnStatusCode: false,
        body: {
            account: JSON.stringify({
                account_num: String(externalAccount.accountNum),
                routing_num: String(externalAccount.routingNum),
            }),
            amount,
            uuid: `decimals-${Date.now()}`,
        },
    })

    it('rejects an amount with more than two decimals', function () {
        postDeposit('10.005').then((resp) => {
            expect(resp.status).to.eq(400)
            expect(resp.body).to.contain('Deposit failed')
            expect(resp.body).to.contain('10.005 has more than two decimal places')
        })
    })

    it('accepts an amount with two decimals', function () {
        postDeposit('10.05').then((resp) => {
            expect(resp.status).to.eq(200)
            expect(resp.body).to.contain('Deposit successful')
        })
    })
})

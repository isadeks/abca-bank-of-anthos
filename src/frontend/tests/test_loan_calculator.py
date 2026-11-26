"""Unit tests for the public /loan-calculator page and its footer link."""

from test_payment_deposit_handlers import HandlerTestCase


class TestLoanCalculator(HandlerTestCase):
    """The loan calculator needs no sign-in and is linked from the footer"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_page(self):
        """/loan-calculator is public and has the form"""
        resp = self.client.get('/loan-calculator')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        for text in ('Loan calculator', 'id="loan-amount"', 'id="loan-rate"',
                     'id="loan-months"', 'id="loan-result"', '<footer'):
            self.assertIn(text, html)

    def test_footer_link(self):
        """Footer links to the page"""
        for path in ('/login', '/signup', '/fees'):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn('href="/loan-calculator"', html)

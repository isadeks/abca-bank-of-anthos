# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Minimal UI translations for the frontend.

English is the source language: templates call ``_('English text')`` and an
unknown text, or any language other than German, is shown unchanged.
"""

DEFAULT_LANGUAGE = 'en'
LANGUAGES = {'en': 'English', 'de': 'Deutsch'}

GERMAN = {
    # navigation and footer
    'Sign out': 'Abmelden',
    'Language': 'Sprache',
    'This website is hosted for demo purposes only. It is not an actual '
    'bank. This is not an official Google project.':
        'Diese Website dient nur zu Demonstrationszwecken. Sie ist keine '
        'echte Bank. Dies ist kein offizielles Google-Projekt.',
    # home page
    'Overview': 'Übersicht',
    'Checking Account': 'Girokonto',
    'Account Number:': 'Kontonummer:',
    'Current Balance': 'Aktueller Kontostand',
    'Deposit Funds': 'Geld einzahlen',
    'Send Payment': 'Zahlung senden',
    'Transaction History': 'Transaktionsverlauf',
    'Error: Could Not Load Transactions':
        'Fehler: Transaktionen konnten nicht geladen werden',
    'No Transactions Found': 'Keine Transaktionen gefunden',
    'Date': 'Datum',
    'Type': 'Typ',
    'Account': 'Konto',
    'Label': 'Bezeichnung',
    'Amount': 'Betrag',
    'Credit': 'Gutschrift',
    'Debit': 'Lastschrift',
    'None': 'Keine',
    'Make a Deposit': 'Einzahlung vornehmen',
    'External Account': 'Externes Konto',
    'New External Account': 'Neues externes Konto',
    'Warning': 'Warnung',
    "This website is a simulation. Please don't include real personal "
    "information.":
        'Diese Website ist eine Simulation. Bitte gib keine echten '
        'persönlichen Daten ein.',
    'Account Number': 'Kontonummer',
    'Routing Number': 'Bankleitzahl',
    'Account Label (Optional)': 'Kontobezeichnung (optional)',
    'Contact Label (Optional)': 'Kontaktbezeichnung (optional)',
    'Invalid label.': 'Ungültige Bezeichnung.',
    'Please enter a valid 10 digit account number.':
        'Bitte gib eine gültige 10-stellige Kontonummer ein.',
    'Please enter a valid 9 digit routing number.':
        'Bitte gib eine gültige 9-stellige Bankleitzahl ein.',
    'Deposit Amount': 'Einzahlungsbetrag',
    'Please enter a valid amount with at most two decimal places.':
        'Bitte gib einen gültigen Betrag mit höchstens zwei '
        'Nachkommastellen ein.',
    'Please enter a valid amount.': 'Bitte gib einen gültigen Betrag ein.',
    'Cancel': 'Abbrechen',
    'Deposit': 'Einzahlen',
    'Send a Payment': 'Zahlung senden',
    'Recipient': 'Empfänger',
    'New Recipient': 'Neuer Empfänger',
    'Transaction Amount': 'Überweisungsbetrag',
    'Send': 'Senden',
    # messages
    'Payment successful': 'Zahlung erfolgreich',
    'Deposit successful': 'Einzahlung erfolgreich',
    'Payment failed': 'Zahlung fehlgeschlagen',
    'Deposit failed': 'Einzahlung fehlgeschlagen',
    'Login Failed': 'Anmeldung fehlgeschlagen',
    'Login failed.': 'Anmeldung fehlgeschlagen.',
    'Error: Invalid client_id': 'Fehler: Ungültige client_id',
    'Error: Invalid redirect_uri': 'Fehler: Ungültige redirect_uri',
    'Error: Account creation failed':
        'Fehler: Kontoerstellung fehlgeschlagen',
    # login
    'Welcome': 'Willkommen',
    'SIGN IN': 'ANMELDEN',
    'Sign in': 'Anmelden',
    'Username': 'Benutzername',
    'Password': 'Passwort',
    'Please enter your username.': 'Bitte gib deinen Benutzernamen ein.',
    'Please enter your password.': 'Bitte gib dein Passwort ein.',
    'Not registered?': 'Noch nicht registriert?',
    'Create an Account': 'Konto erstellen',
    # consent
    'Do you consent?': 'Stimmst du zu?',
    'is requesting access to your account information':
        'fordert Zugriff auf deine Kontoinformationen an',
    'Approve': 'Zustimmen',
    'Deny': 'Ablehnen',
    # signup
    'Back': 'Zurück',
    'Register a new account': 'Neues Konto registrieren',
    'Account Information': 'Kontoinformationen',
    "Passwords don't match. Please try again.":
        'Die Passwörter stimmen nicht überein. Bitte versuche es erneut.',
    'Confirm Password': 'Passwort bestätigen',
    'Create Account': 'Konto erstellen',
}

TRANSLATIONS = {'de': GERMAN}


def normalize_language(code):
    """Returns a supported language code, or the default for anything else"""
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def translate(text, language):
    """
    Translates an English UI text.

    A text with a detail after the first colon ("Payment failed: reason") is
    translated up to the colon so the backend's detail is kept as is. Unknown
    texts and the default language are returned unchanged.
    """
    table = TRANSLATIONS.get(language)
    if not table or not isinstance(text, str):
        return text
    if text in table:
        return table[text]
    head, sep, detail = text.partition(': ')
    if sep and head in table:
        return f'{table[head]}: {detail}'
    return text

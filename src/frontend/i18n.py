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
Minimal translations for the frontend UI.

English is the source language: a template or handler passes the English text
to ``translate`` and gets the text back unchanged for English, or for any text
that has no entry, so a missing translation never breaks a page.
"""

DEFAULT_LANGUAGE = 'en'
LANGUAGE_COOKIE = 'lang'

# code -> name of the language in that language, shown by the language switcher
LANGUAGES = {'en': 'English', 'fr': 'Français'}

FRENCH = {
    # navigation and footer
    'Sign out': 'Se déconnecter',
    'Language': 'Langue',
    'Cluster: ': 'Cluster : ',
    'Pod: ': 'Pod : ',
    'Zone: ': 'Zone : ',
    'This website is hosted for demo purposes only. It is not an actual '
    'bank. This is not an official Google project.':
        'Ce site est hébergé à des fins de démonstration uniquement. Il ne '
        "s'agit pas d'une vraie banque. Ce n'est pas un projet officiel de "
        'Google.',
    'Toggle navigation': 'Afficher ou masquer la navigation',
    # login
    'Welcome': 'Bienvenue',
    'Sign in': 'Se connecter',
    'SIGN IN': 'SE CONNECTER',
    'Login failed.': 'Échec de la connexion.',
    'Username': "Nom d'utilisateur",
    'Please enter your username.': "Veuillez saisir votre nom d'utilisateur.",
    'Password': 'Mot de passe',
    'Please enter your password.': 'Veuillez saisir votre mot de passe.',
    'Not registered?': 'Pas encore inscrit ?',
    'Create an Account': 'Créer un compte',
    # consent
    'is requesting access to your account information':
        "demande l'accès aux informations de votre compte",
    'Do you consent?': 'Donnez-vous votre accord ?',
    'Approve': 'Approuver',
    'Deny': 'Refuser',
    # signup
    'Back': 'Retour',
    'Register a new account': 'Créer un nouveau compte',
    'Account Information': 'Informations du compte',
    "Passwords don't match. Please try again.":
        'Les mots de passe ne correspondent pas. Veuillez réessayer.',
    'Please enter a valid username. Username must be 2 to 15 characters in '
    'length and contain only alphanumeric or underscore characters.':
        "Veuillez saisir un nom d'utilisateur valide. Il doit comporter de 2 "
        'à 15 caractères alphanumériques ou tirets bas.',
    'Please enter a password.': 'Veuillez saisir un mot de passe.',
    'Confirm Password': 'Confirmer le mot de passe',
    'Please confirm your password.': 'Veuillez confirmer votre mot de passe.',
    'Personal Information': 'Informations personnelles',
    'Some fields are read-only for this demo for security purposes.':
        'Certains champs sont en lecture seule dans cette démo pour des '
        'raisons de sécurité.',
    'First name': 'Prénom',
    'Valid first name is required.': 'Un prénom valide est requis.',
    'Last name': 'Nom',
    'Valid last name is required.': 'Un nom valide est requis.',
    'Address': 'Adresse',
    'Please enter your address.': 'Veuillez saisir votre adresse.',
    'Country': 'Pays',
    'Please select a valid country.': 'Veuillez sélectionner un pays valide.',
    'State': 'État',
    'Please provide a valid state.': 'Veuillez indiquer un état valide.',
    'Choose...': 'Choisir...',
    'Zip': 'Code postal',
    'Zip code required.': 'Le code postal est requis.',
    'SSN': 'N° de sécurité sociale',
    'Valid SSN is required.': 'Un numéro de sécurité sociale valide est requis.',
    'Birthday': 'Date de naissance',
    'Valid birthday is required.': 'Une date de naissance valide est requise.',
    'Timezone': 'Fuseau horaire',
    'Please select a valid timezone.':
        'Veuillez sélectionner un fuseau horaire valide.',
    'Create Account': 'Créer le compte',
    # home
    'Overview': "Vue d'ensemble",
    'Checking Account': 'Compte courant',
    'Account Number:': 'Numéro de compte :',
    'Current Balance': 'Solde actuel',
    'Deposit Funds': 'Déposer des fonds',
    'Send Payment': 'Envoyer un paiement',
    'Transaction History': 'Historique des transactions',
    'Error: Could Not Load Transactions':
        "Erreur : impossible de charger les transactions",
    'No Transactions Found': 'Aucune transaction trouvée',
    'Date': 'Date',
    'Type': 'Type',
    'Account': 'Compte',
    'Label': 'Libellé',
    'Amount': 'Montant',
    'Credit': 'Crédit',
    'Debit': 'Débit',
    'None': 'Aucun',
    'Make a Deposit': 'Effectuer un dépôt',
    'Close': 'Fermer',
    'External Account': 'Compte externe',
    'New External Account': 'Nouveau compte externe',
    'Warning': 'Attention',
    ": This website is a simulation. Please don't include real personal "
    "information.":
        " : ce site est une simulation. N'indiquez pas de véritables "
        'informations personnelles.',
    'Account Number': 'Numéro de compte',
    'Please enter a valid 10 digit account number.':
        'Veuillez saisir un numéro de compte valide à 10 chiffres.',
    'Routing Number': "Numéro d'acheminement",
    'Please enter a valid 9 digit routing number.':
        "Veuillez saisir un numéro d'acheminement valide à 9 chiffres.",
    'Account Label (Optional)': 'Libellé du compte (facultatif)',
    'Invalid label.': 'Libellé non valide.',
    'Deposit Amount': 'Montant du dépôt',
    'Please enter a valid amount with at most two decimal places.':
        'Veuillez saisir un montant valide avec au plus deux décimales.',
    'Cancel': 'Annuler',
    'Deposit': 'Déposer',
    'Send a Payment': 'Envoyer un paiement',
    'Recipient': 'Destinataire',
    'New Recipient': 'Nouveau destinataire',
    'Contact Label (Optional)': 'Libellé du contact (facultatif)',
    'Transaction Amount': 'Montant de la transaction',
    'Please enter a valid amount.': 'Veuillez saisir un montant valide.',
    'Send': 'Envoyer',
    # messages from the handlers
    'Payment successful': 'Paiement effectué',
    'Deposit successful': 'Dépôt effectué',
    'Payment failed': 'Échec du paiement',
    'Deposit failed': 'Échec du dépôt',
    'missing form field': 'champ de formulaire manquant',
    'invalid routing number': "numéro d'acheminement non valide",
    '{value} is not a valid number': "{value} n'est pas un nombre valide",
    'Error: Account creation failed': 'Erreur : échec de la création du compte',
    'Error: Invalid client_id': 'Erreur : client_id non valide',
    'Error: Invalid redirect_uri': 'Erreur : redirect_uri non valide',
}

TRANSLATIONS = {'fr': FRENCH}

FRENCH_MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
                 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']


def translate(text, lang=DEFAULT_LANGUAGE):
    """The text in the language, or the text itself if it has no translation"""
    return TRANSLATIONS.get(lang, {}).get(text, text)


def month_abbreviation(month, lang=DEFAULT_LANGUAGE):
    """Short name of the month (1-12) in the language"""
    if lang == 'fr':
        return FRENCH_MONTHS[month - 1]
    return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1]


def choose_language(requested, cookie, accept_languages):
    """
    The language to serve, in order of preference: the one requested with
    ?lang=, the one saved in the cookie, the first supported language in the
    Accept-Language header (a list of (language, quality) pairs, best first),
    then English.
    """
    for candidate in (requested, cookie):
        if candidate in LANGUAGES:
            return candidate
    for language, _quality in accept_languages:
        primary = language.lower().split('-')[0]
        if primary in LANGUAGES:
            return primary
    return DEFAULT_LANGUAGE

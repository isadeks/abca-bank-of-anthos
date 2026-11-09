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

"""Minimal translations for the frontend (English and Spanish)

English strings are the keys. Anything without a Spanish translation is shown
in English, so untranslated pages and backend messages keep working.
"""

DEFAULT_LANG = 'en'
LANGUAGES = {'en': 'English', 'es': 'Español'}
LANG_COOKIE = 'lang'

SPANISH = {
    # Navigation
    'Sign out': 'Cerrar sesión',
    'Language': 'Idioma',
    # Login
    'Welcome': 'Bienvenido',
    'SIGN IN': 'INICIAR SESIÓN',
    'Login failed.': 'Error al iniciar sesión.',
    'Username': 'Usuario',
    'Password': 'Contraseña',
    'Please enter your username.': 'Por favor, introduce tu usuario.',
    'Please enter your password.': 'Por favor, introduce tu contraseña.',
    'Sign in': 'Iniciar sesión',
    'Not registered?': '¿No tienes cuenta?',
    'Create an Account': 'Crear una cuenta',
    'Error: Account creation failed': 'Error: no se pudo crear la cuenta',
    'Error: Invalid client_id': 'Error: client_id no válido',
    'Error: Invalid redirect_uri': 'Error: redirect_uri no válido',
    # Home
    'Overview': 'Resumen',
    'Checking Account': 'Cuenta corriente',
    'Account Number:': 'Número de cuenta:',
    'Current Balance': 'Saldo actual',
    'Deposit Funds': 'Depositar fondos',
    'Send Payment': 'Enviar pago',
    'Transaction History': 'Historial de transacciones',
    'Error: Could Not Load Transactions':
        'Error: no se pudieron cargar las transacciones',
    'No Transactions Found': 'No se encontraron transacciones',
    'Date': 'Fecha',
    'Type': 'Tipo',
    'Account': 'Cuenta',
    'Label': 'Etiqueta',
    'Amount': 'Importe',
    'Credit': 'Crédito',
    'Debit': 'Débito',
    'None': 'Ninguna',
    # Deposit
    'Make a Deposit': 'Hacer un depósito',
    'External Account': 'Cuenta externa',
    'New External Account': 'Nueva cuenta externa',
    'Warning': 'Aviso',
    'This website is a simulation. Please don\'t include real personal '
    'information.':
        'Este sitio web es una simulación. No incluyas información '
        'personal real.',
    'Account Number': 'Número de cuenta',
    'Routing Number': 'Número de ruta',
    'Account Label (Optional)': 'Etiqueta de la cuenta (opcional)',
    'Please enter a valid 10 digit account number.':
        'Por favor, introduce un número de cuenta válido de 10 dígitos.',
    'Please enter a valid 9 digit routing number.':
        'Por favor, introduce un número de ruta válido de 9 dígitos.',
    'Invalid label.': 'Etiqueta no válida.',
    'Deposit Amount': 'Importe del depósito',
    'Please enter a valid amount.': 'Por favor, introduce un importe válido.',
    'Cancel': 'Cancelar',
    'Deposit': 'Depositar',
    # Payment
    'Send a Payment': 'Enviar un pago',
    'Recipient': 'Destinatario',
    'New Recipient': 'Nuevo destinatario',
    'Contact Label (Optional)': 'Etiqueta del contacto (opcional)',
    'Transaction Amount': 'Importe de la transacción',
    'Send': 'Enviar',
    # Footer
    'This website is hosted for demo purposes only. It is not an actual '
    'bank. This is not an official Google project.':
        'Este sitio web se aloja solo con fines de demostración. No es un '
        'banco real. No es un proyecto oficial de Google.',
    # Messages shown after a payment or deposit
    'Payment successful': 'Pago realizado con éxito',
    'Deposit successful': 'Depósito realizado con éxito',
    'Payment failed': 'Error en el pago',
    'Deposit failed': 'Error en el depósito',
    'invalid routing number': 'número de ruta no válido',
    'missing form field': 'falta un campo del formulario',
}

TRANSLATIONS = {'es': SPANISH}


def normalize_lang(lang):
    """Return a supported language code, falling back to the default"""
    return lang if lang in LANGUAGES else DEFAULT_LANG


def translate(text, lang):
    """Translate an English string; unknown strings are returned unchanged"""
    return TRANSLATIONS.get(normalize_lang(lang), {}).get(text, text)


def not_a_number(value, lang):
    """The message for an amount that is not a valid number"""
    if normalize_lang(lang) == 'es':
        return f'{value} no es un número válido'
    return f'{value} is not a valid number'

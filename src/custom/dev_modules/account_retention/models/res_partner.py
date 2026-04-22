from odoo import fields, models

FISCAL_PROFILE_SELECTION = [
    ('standard', 'Estándar'),
    ('agent', 'Agente de Retención'),
    ('exempt', 'Exento'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_fiscal_profile = fields.Selection(
        selection=FISCAL_PROFILE_SELECTION,
        string='Perfil Fiscal',
        default='standard',
        help=(
            'Define el comportamiento de retención para este partner:\n'
            '- Estándar: sin retención especial.\n'
            '- Agente de Retención: se aplica la retención correspondiente.\n'
            '- Exento: no se aplica ninguna retención.'
        ),
    )

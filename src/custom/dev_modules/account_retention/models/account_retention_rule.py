from odoo import fields, models

FISCAL_PROFILE_SELECTION = [
    ('standard', 'Estándar'),
    ('agent', 'Agente de Retención'),
    ('exempt', 'Exento'),
]


class AccountRetentionRule(models.Model):
    _name = 'account.retention.rule'
    _description = 'Regla de Retención Fiscal'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    fiscal_profile = fields.Selection(
        selection=FISCAL_PROFILE_SELECTION,
        string='Perfil Fiscal',
        required=True,
        help='Perfil fiscal del partner al que aplica esta regla.',
    )
    retention_rate = fields.Float(
        string='Tasa de Retención (%)',
        digits=(5, 2),
        default=0.0,
        help='Porcentaje a retener sobre el monto de la factura (ej. 5.0 para 5%).',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta Contable',
        ondelete='restrict',
        help='Cuenta contable donde se registra el monto retenido.',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

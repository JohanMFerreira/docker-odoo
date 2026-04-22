# -*- coding: utf-8 -*-
from odoo import fields, models

RISK_LEVEL_SELECTION = [
    ('low', 'Bajo'),
    ('medium', 'Medio'),
    ('high', 'Alto'),
    ('critical', 'Crítico'),
]

# Orden de severidad: cuanto mayor el índice, más severo
RISK_SEVERITY_ORDER = {
    'low': 1,
    'medium': 2,
    'high': 3,
    'critical': 4,
}


class AccountCollectionAlertRule(models.Model):
    _name = 'account.collection.alert.rule'
    _description = 'Regla de Alerta de Cobro'
    _order = 'risk_level desc, days_overdue desc'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    days_overdue = fields.Integer(
        string='Días de Atraso Mínimos',
        default=0,
        help='Número mínimo de días vencidos para activar esta regla.',
    )
    amount_min = fields.Float(
        string='Monto Mínimo Vencido',
        default=0.0,
        help='Monto residual mínimo para activar esta regla.',
    )
    risk_level = fields.Selection(
        selection=RISK_LEVEL_SELECTION,
        string='Nivel de Riesgo',
        required=True,
        index=True,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

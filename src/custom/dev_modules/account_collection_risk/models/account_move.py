# -*- coding: utf-8 -*-
from odoo import api, fields, models

RISK_LEVEL_WITH_NONE = [
    ('none', 'Sin Riesgo'),
    ('low', 'Bajo'),
    ('medium', 'Medio'),
    ('high', 'Alto'),
    ('critical', 'Crítico'),
]

# Mapa de severidad para ordenar reglas de mayor a menor
_SEVERITY = {
    'critical': 4,
    'high': 3,
    'medium': 2,
    'low': 1,
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_risk_level = fields.Selection(
        selection=RISK_LEVEL_WITH_NONE,
        string='Nivel de Riesgo de Cobro',
        compute='_compute_x_risk_level',
        store=True,
        index=True,
        default='none',
        help=(
            'Nivel de riesgo calculado automáticamente a partir de las reglas '
            'de alerta de cobro activas.'
        ),
    )

    @api.depends(
        'invoice_date_due',
        'amount_residual',
        'payment_state',
        'state',
        'move_type',
    )
    def _compute_x_risk_level(self):
        """Calcula el nivel de riesgo de cobro para cada factura.

        Solo aplica a facturas de cliente (out_invoice) publicadas y no
        totalmente pagadas. Evalúa las reglas activas ordenadas de mayor a
        menor severidad; asigna la primera regla cuyos criterios se cumplen.
        """
        today = fields.Date.today()

        # Cargar reglas activas ordenadas de mayor a menor severidad
        rules = self.env['account.collection.alert.rule'].search(
            [('active', '=', True)]
        )
        # Ordenar en Python para garantizar critical → high → medium → low
        rules_sorted = sorted(
            rules,
            key=lambda r: _SEVERITY.get(r.risk_level, 0),
            reverse=True,
        )

        for move in self:
            if (
                move.move_type != 'out_invoice'
                or move.state != 'posted'
                or move.payment_state == 'paid'
            ):
                move.x_risk_level = 'none'
                continue

            if not move.invoice_date_due or move.invoice_date_due >= today:
                move.x_risk_level = 'none'
                continue

            days_overdue = (today - move.invoice_date_due).days
            amount_residual = move.amount_residual

            assigned_level = 'none'
            for rule in rules_sorted:
                if (
                    days_overdue >= rule.days_overdue
                    and amount_residual >= rule.amount_min
                ):
                    assigned_level = rule.risk_level
                    break

            move.x_risk_level = assigned_level

    def action_recompute_risk_level(self):
        """Método invocado por el cron para recalcular el nivel de riesgo."""
        invoices = self.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid'),
        ])
        invoices._compute_x_risk_level()

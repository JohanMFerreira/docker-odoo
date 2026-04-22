# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosDiscountRule(models.Model):
    _name = 'pos.discount.rule'
    _description = 'Regla de Descuento Horario TPV'
    _order = 'hour_from'

    name = fields.Char(string='Nombre', required=True)
    hour_from = fields.Float(
        string='Hora Desde',
        help='Inicio del intervalo horario (p. ej. 12.0 = 12:00, 13.5 = 13:30).',
    )
    hour_to = fields.Float(
        string='Hora Hasta',
        help='Fin del intervalo horario (exclusivo).',
    )
    discount_percentage = fields.Float(
        string='Descuento (%)',
        digits=(5, 2),
        help='Porcentaje a aplicar en todas las líneas del pedido TPV.',
    )
    active = fields.Boolean(string='Activo', default=True)

    # ------------------------------------------------------------------
    # Restricciones
    # ------------------------------------------------------------------

    @api.constrains('hour_from', 'hour_to')
    def _check_hour_range(self):
        for rule in self:
            if rule.hour_from >= rule.hour_to:
                raise ValidationError(
                    'La hora de inicio (Hora Desde) debe ser estrictamente menor '
                    'que la hora de fin (Hora Hasta) en la regla "%s".' % rule.name
                )

    @api.constrains('discount_percentage')
    def _check_discount_percentage(self):
        for rule in self:
            if not (0.0 <= rule.discount_percentage <= 100.0):
                raise ValidationError(
                    'El porcentaje de descuento debe estar entre 0 y 100 '
                    'para la regla "%s".' % rule.name
                )

    @api.constrains('hour_from', 'hour_to', 'active')
    def _check_no_overlap(self):
        """Verifica que no haya dos reglas activas con intervalos horarios solapados."""
        for rule in self:
            if not rule.active:
                continue
            overlapping = self.search([
                ('id', '!=', rule.id),
                ('active', '=', True),
                ('hour_from', '<', rule.hour_to),
                ('hour_to', '>', rule.hour_from),
            ])
            if overlapping:
                names = ', '.join(overlapping.mapped('name'))
                raise ValidationError(
                    'El intervalo horario de la regla "%s" se solapa con: %s.'
                    % (rule.name, names)
                )

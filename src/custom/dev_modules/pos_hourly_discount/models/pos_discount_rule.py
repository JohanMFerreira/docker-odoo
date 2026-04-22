# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosDiscountRule(models.Model):
    _name = 'pos.discount.rule'
    _description = 'POS Hourly Discount Rule'
    _order = 'hour_from'

    name = fields.Char(string='Name', required=True)
    hour_from = fields.Float(
        string='Hour From',
        help='Start of the time range (e.g. 12.0 = 12:00, 13.5 = 13:30).',
    )
    hour_to = fields.Float(
        string='Hour To',
        help='End of the time range (exclusive).',
    )
    discount_percentage = fields.Float(
        string='Discount (%)',
        digits=(5, 2),
        help='Percentage to apply to all POS order lines.',
    )
    active = fields.Boolean(string='Active', default=True)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('hour_from', 'hour_to')
    def _check_hour_range(self):
        for rule in self:
            if rule.hour_from >= rule.hour_to:
                raise ValidationError(
                    'The start time (Hour From) must be strictly less than '
                    'the end time (Hour To) for rule "%s".' % rule.name
                )

    @api.constrains('discount_percentage')
    def _check_discount_percentage(self):
        for rule in self:
            if not (0.0 <= rule.discount_percentage <= 100.0):
                raise ValidationError(
                    'The discount percentage must be between 0 and 100 '
                    'for rule "%s".' % rule.name
                )

    @api.constrains('hour_from', 'hour_to', 'active')
    def _check_no_overlap(self):
        """Ensure no two active rules have overlapping time ranges."""
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
                    'The time range of rule "%s" overlaps with: %s.'
                    % (rule.name, names)
                )

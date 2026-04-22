# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    x_discount_rule_id = fields.Many2one(
        comodel_name='pos.discount.rule',
        string='Applied Discount Rule',
        readonly=True,
        copy=False,
        help='Hourly discount rule that was automatically applied to this order.',
    )

    # ------------------------------------------------------------------
    # Override _process_order
    # ------------------------------------------------------------------

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Create the POS order via super(), then apply hourly discount."""
        order_id = super()._process_order(order, draft, existing_order)

        try:
            order_obj = self.env['pos.order'].browse(order_id)
            self._apply_hourly_discount(order_obj)
        except Exception:
            # Never block order creation due to discount logic errors.
            _logger.exception(
                'pos_hourly_discount: unexpected error while applying '
                'discount to order %s', order_id
            )

        return order_id

    def _apply_hourly_discount(self, order_obj):
        """Find the matching active rule and apply its discount."""
        if not order_obj or not order_obj.exists():
            return

        date_order = order_obj.date_order or fields.Datetime.now()
        # Convert to a naive local-like float hour using the server timezone.
        # date_order is stored in UTC; for simplicity we work in UTC hours.
        # If the business needs local time, convert via pytz here.
        hour = date_order.hour + date_order.minute / 60.0

        rule = self.env['pos.discount.rule'].search([
            ('active', '=', True),
            ('hour_from', '<=', hour),
            ('hour_to', '>', hour),
        ], limit=1)

        if not rule:
            return

        discount = rule.discount_percentage
        for line in order_obj.lines:
            line.discount = discount

        order_obj.x_discount_rule_id = rule.id
        _logger.info(
            'pos_hourly_discount: applied rule "%s" (%.2f%%) to order %s',
            rule.name, discount, order_obj.name,
        )

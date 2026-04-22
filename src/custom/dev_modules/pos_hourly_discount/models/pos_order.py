# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    x_discount_rule_id = fields.Many2one(
        comodel_name='pos.discount.rule',
        string='Regla de Descuento Aplicada',
        readonly=True,
        copy=False,
        help='Regla de descuento horario aplicada automáticamente a este pedido.',
    )

    # ------------------------------------------------------------------
    # Sobreescritura de _process_order
    # ------------------------------------------------------------------

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Crea el pedido TPV mediante super() y luego aplica el descuento horario."""
        order_id = super()._process_order(order, draft, existing_order)

        try:
            order_obj = self.env['pos.order'].browse(order_id)
            self._apply_hourly_discount(order_obj)
        except Exception:
            # Nunca bloquear la creación del pedido por errores en la lógica de descuentos.
            _logger.exception(
                'pos_hourly_discount: error inesperado al aplicar '
                'descuento al pedido %s', order_id
            )

        return order_id

    def _apply_hourly_discount(self, order_obj):
        """Busca la regla activa correspondiente y aplica su descuento."""
        if not order_obj or not order_obj.exists():
            return

        date_order = order_obj.date_order or fields.Datetime.now()
        # Convierte la hora a un float usando la zona horaria del servidor.
        # date_order se almacena en UTC; por simplicidad se trabaja en horas UTC.
        # Si se necesita la hora local del negocio, convertir con pytz aquí.
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
            'pos_hourly_discount: regla "%s" (%.2f%%) aplicada al pedido %s',
            rule.name, discount, order_obj.name,
        )

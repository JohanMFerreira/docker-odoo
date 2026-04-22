import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

INVOICE_TYPES = ['out_invoice', 'in_invoice']


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_retention_rule_id = fields.Many2one(
        comodel_name='account.retention.rule',
        string='Regla de Retención Aplicada',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='Regla de retención que fue aplicada al validar esta factura.',
    )

    x_retention_applied = fields.Boolean(
        string='Retención Aplicada',
        compute='_compute_x_retention_applied',
        store=False,
        help='Indica si se aplicó una retención al validar esta factura.',
    )

    @api.depends('x_retention_rule_id')
    def _compute_x_retention_applied(self):
        for move in self:
            move.x_retention_applied = bool(move.x_retention_rule_id)

    def _get_retention_rule(self, fiscal_profile):
        """Busca la primera regla de retención activa para el perfil fiscal dado."""
        return self.env['account.retention.rule'].sudo().search(
            [('fiscal_profile', '=', fiscal_profile), ('active', '=', True)],
            limit=1,
        )

    def _apply_retention(self):
        """
        Evalúa si corresponde aplicar retención y, en caso afirmativo,
        agrega la línea contable y registra la regla usada.
        Debe llamarse después de que la factura esté en estado 'posted'.

        Estrategia dos pasos para Odoo 17:
        1. Crear la línea (precompute _compute_balance la deja en 0 para facturas).
        2. Escribir balance directamente — no re-dispara _compute_balance porque
           @api.depends('move_id') solo se activa cuando move_id cambia.
        """
        self.ensure_one()

        if self.move_type not in INVOICE_TYPES:
            return False

        fiscal_profile = self.partner_id.x_fiscal_profile
        if not fiscal_profile or fiscal_profile == 'exempt':
            return False

        rule = self._get_retention_rule(fiscal_profile)
        if not rule:
            _logger.info(
                'No se encontró regla de retención para el perfil "%s" '
                'en la factura %s.',
                fiscal_profile,
                self.name or self.id,
            )
            return False

        if not rule.account_id:
            _logger.warning(
                'La regla de retención "%s" no tiene cuenta contable configurada. '
                'No se aplicará retención en la factura %s.',
                rule.name,
                self.name or self.id,
            )
            return False

        taxable_amount = sum(self.invoice_line_ids.mapped('price_subtotal'))
        retention_amount = taxable_amount * (rule.retention_rate / 100.0)
        balance = retention_amount if self.move_type == 'out_invoice' else -retention_amount

        # display_type='tax' omite el primer bucle de _sync_invoice (que reinicia
        # amount_currency a 0 para líneas de tipo 'product').
        # El segundo bucle establece balance = amount_currency / currency_rate.
        # Pasar solo amount_currency (sin balance/debit/credit) hace que
        # _prepare_create_values elimine el balance=0 precalculado del INSERT.
        self.env['account.move.line'].with_context(
            check_move_validity=False
        ).create({
            'move_id': self.id,
            'account_id': rule.account_id.id,
            'name': 'Retención: %s (%.2f%%)' % (rule.name, rule.retention_rate),
            'currency_id': self.currency_id.id,
            'amount_currency': balance,
            'display_type': 'tax',
        })

        self.sudo().write({'x_retention_rule_id': rule.id})
        return True

    def action_post(self):
        result = super().action_post()
        for move in self:
            if move.move_type in INVOICE_TYPES and move.state == 'posted':
                move._apply_retention()
        return result

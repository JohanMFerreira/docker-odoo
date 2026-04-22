# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountCollectionRisk(TransactionCase):
    """Tests para el módulo account_collection_risk."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ---- Partner de prueba ----
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Test Riesgo',
            'customer_rank': 1,
        })

        # ---- Cuenta de ingresos y diario de ventas ----
        cls.account_revenue = cls.env['account.account'].search([
            ('account_type', '=', 'income'),
        ], limit=1)
        cls.journal_sale = cls.env['account.journal'].search([
            ('type', '=', 'sale'),
        ], limit=1)

        # ---- Reglas de alerta ----
        cls.rule_low = cls.env['account.collection.alert.rule'].create({
            'name': 'Bajo - 10 días / 100',
            'days_overdue': 10,
            'amount_min': 100.0,
            'risk_level': 'low',
            'active': True,
        })
        cls.rule_medium = cls.env['account.collection.alert.rule'].create({
            'name': 'Medio - 30 días / 500',
            'days_overdue': 30,
            'amount_min': 500.0,
            'risk_level': 'medium',
            'active': True,
        })
        cls.rule_high = cls.env['account.collection.alert.rule'].create({
            'name': 'Alto - 60 días / 1000',
            'days_overdue': 60,
            'amount_min': 1000.0,
            'risk_level': 'high',
            'active': True,
        })
        cls.rule_critical = cls.env['account.collection.alert.rule'].create({
            'name': 'Crítico - 90 días / 2000',
            'days_overdue': 90,
            'amount_min': 2000.0,
            'risk_level': 'critical',
            'active': True,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_invoice(self, days_overdue, amount, post=True):
        """Crea y opcionalmente confirma una factura de cliente."""
        today = fields.Date.today()
        due_date = today - timedelta(days=days_overdue)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': due_date,
            'invoice_date_due': due_date,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba',
                'quantity': 1,
                'price_unit': amount,
                'account_id': self.account_revenue.id,
            })],
        })
        if post:
            invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Tests de modelo account.collection.alert.rule
    # ------------------------------------------------------------------

    def test_rule_creation(self):
        """Las reglas se crean correctamente con sus atributos."""
        self.assertEqual(self.rule_low.name, 'Bajo - 10 días / 100')
        self.assertEqual(self.rule_low.risk_level, 'low')
        self.assertEqual(self.rule_low.days_overdue, 10)
        self.assertAlmostEqual(self.rule_low.amount_min, 100.0)
        self.assertTrue(self.rule_low.active)

    def test_rule_archive(self):
        """Archivar una regla la excluye del cálculo."""
        rule_extra = self.env['account.collection.alert.rule'].create({
            'name': 'Regla extra archivada',
            'days_overdue': 5,
            'amount_min': 50.0,
            'risk_level': 'low',
            'active': True,
        })
        rule_extra.active = False
        active_rules = self.env['account.collection.alert.rule'].search([
            ('active', '=', True),
            ('id', '=', rule_extra.id),
        ])
        self.assertFalse(active_rules)

    # ------------------------------------------------------------------
    # Tests de cálculo de nivel de riesgo
    # ------------------------------------------------------------------

    def test_risk_none_for_not_posted(self):
        """Facturas en borrador no tienen nivel de riesgo."""
        invoice = self._make_invoice(days_overdue=120, amount=5000.0, post=False)
        # Forzar fecha manualmente ya que no está publicada
        invoice.invoice_date_due = fields.Date.today() - timedelta(days=120)
        invoice._compute_x_risk_level()
        self.assertEqual(invoice.x_risk_level, 'none')

    def test_risk_none_for_vendor_bill(self):
        """Facturas de proveedor no reciben nivel de riesgo."""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.today() - timedelta(days=100),
            'invoice_date_due': fields.Date.today() - timedelta(days=100),
            'journal_id': self.env['account.journal'].search(
                [('type', '=', 'purchase')], limit=1
            ).id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Compra test',
                'quantity': 1,
                'price_unit': 5000.0,
                'account_id': self.account_revenue.id,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.x_risk_level, 'none')

    def test_risk_none_when_not_overdue(self):
        """Factura con vencimiento hoy o futuro no tiene riesgo."""
        today = fields.Date.today()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': today,
            'invoice_date_due': today,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Factura vigente',
                'quantity': 1,
                'price_unit': 5000.0,
                'account_id': self.account_revenue.id,
            })],
        })
        invoice.action_post()
        self.assertEqual(invoice.x_risk_level, 'none')

    def test_risk_none_when_no_matching_rule(self):
        """Factura vencida que no alcanza ningún umbral = sin riesgo."""
        # 5 días vencida, monto 50 → no cumple ninguna regla (mínimo 10 días / 100)
        invoice = self._make_invoice(days_overdue=5, amount=50.0)
        self.assertEqual(invoice.x_risk_level, 'none')

    def test_risk_low(self):
        """Factura que cumple criterios de riesgo bajo."""
        # 15 días vencida, 200 → cumple 'low' (10d/100) pero no 'medium' (30d/500)
        invoice = self._make_invoice(days_overdue=15, amount=200.0)
        self.assertEqual(invoice.x_risk_level, 'low')

    def test_risk_medium(self):
        """Factura que cumple criterios de riesgo medio."""
        # 35 días vencida, 600 → cumple 'medium' (30d/500) pero no 'high' (60d/1000)
        invoice = self._make_invoice(days_overdue=35, amount=600.0)
        self.assertEqual(invoice.x_risk_level, 'medium')

    def test_risk_high(self):
        """Factura que cumple criterios de riesgo alto."""
        # 65 días vencida, 1200 → cumple 'high' (60d/1000) pero no 'critical' (90d/2000)
        invoice = self._make_invoice(days_overdue=65, amount=1200.0)
        self.assertEqual(invoice.x_risk_level, 'high')

    def test_risk_critical(self):
        """Factura que cumple criterios de riesgo crítico."""
        # 100 días vencida, 3000 → cumple 'critical' (90d/2000)
        invoice = self._make_invoice(days_overdue=100, amount=3000.0)
        self.assertEqual(invoice.x_risk_level, 'critical')

    def test_severity_order_critical_wins(self):
        """La regla más severa que aplica gana sobre las menos severas."""
        # 95 días vencida, 2500 → cumple critical, high, medium y low
        invoice = self._make_invoice(days_overdue=95, amount=2500.0)
        self.assertEqual(
            invoice.x_risk_level,
            'critical',
            'La regla más severa (critical) debe tener precedencia.',
        )

    def test_amount_threshold_respected(self):
        """Si el monto no alcanza el umbral, se asigna un nivel inferior."""
        # 95 días vencida pero monto 1500 → no cumple critical (2000) ni high (1000)?
        # Sí cumple high (1000) y medium (500) y low (100)
        invoice = self._make_invoice(days_overdue=95, amount=1500.0)
        self.assertEqual(invoice.x_risk_level, 'high')

    def test_days_threshold_respected(self):
        """Si los días no alcanzan el umbral, se asigna un nivel inferior."""
        # 50 días vencida, 3000 → no cumple critical (90d) ni high (60d)
        # Sí cumple medium (30d/500) y low (10d/100)
        invoice = self._make_invoice(days_overdue=50, amount=3000.0)
        self.assertEqual(invoice.x_risk_level, 'medium')

    def test_risk_none_after_payment(self):
        """Una factura pagada pierde el nivel de riesgo."""
        invoice = self._make_invoice(days_overdue=100, amount=3000.0)
        self.assertEqual(invoice.x_risk_level, 'critical')

        # Registrar pago completo
        payment_wizard = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({})
        payment_wizard.action_create_payments()

        invoice._compute_x_risk_level()
        self.assertEqual(
            invoice.x_risk_level,
            'none',
            'Una factura totalmente pagada debe tener nivel de riesgo "none".',
        )

    def test_action_recompute_risk_level(self):
        """El método del cron recalcula correctamente."""
        invoice_critical = self._make_invoice(days_overdue=100, amount=3000.0)
        invoice_low = self._make_invoice(days_overdue=15, amount=200.0)

        # Forzar reset para simular que el cron se ejecuta
        invoice_critical.write({'x_risk_level': 'none'})
        invoice_low.write({'x_risk_level': 'none'})

        self.env['account.move'].action_recompute_risk_level()

        self.assertEqual(invoice_critical.x_risk_level, 'critical')
        self.assertEqual(invoice_low.x_risk_level, 'low')

    def test_inactive_rule_ignored(self):
        """Las reglas inactivas no se usan en el cálculo."""
        self.rule_critical.active = False
        try:
            # 100 días vencida, 3000 → sin rule_critical, debe quedar en 'high'
            invoice = self._make_invoice(days_overdue=100, amount=3000.0)
            self.assertEqual(
                invoice.x_risk_level,
                'high',
                'Sin regla critical activa, debe asignarse el siguiente nivel.',
            )
        finally:
            self.rule_critical.active = True

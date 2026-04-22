from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAccountRetention(TransactionCase):
    """Tests para la aplicación automática de retenciones fiscales."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Obtener o crear un diario de ventas
        cls.journal_sale = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.env.company.id)],
            limit=1,
        )

        # Cuenta de ingresos para las líneas de factura
        cls.account_income = cls.env['account.account'].search(
            [
                ('account_type', '=', 'income'),
                ('company_id', '=', cls.env.company.id),
            ],
            limit=1,
        )

        # Cuenta contable de retención (cuenta de tipo corriente o por cobrar)
        cls.account_retention = cls.env['account.account'].search(
            [
                ('account_type', 'in', ['asset_current', 'asset_receivable']),
                ('company_id', '=', cls.env.company.id),
                ('reconcile', '=', False),
            ],
            limit=1,
        )
        if not cls.account_retention:
            cls.account_retention = cls.env['account.account'].search(
                [('company_id', '=', cls.env.company.id)],
                limit=1,
            )

        # Regla de retención para el perfil 'agent'
        cls.retention_rule_agent = cls.env['account.retention.rule'].create({
            'name': 'Retención Agente 5%',
            'fiscal_profile': 'agent',
            'retention_rate': 5.0,
            'account_id': cls.account_retention.id,
            'active': True,
        })

        # Regla de retención para el perfil 'standard'
        cls.retention_rule_standard = cls.env['account.retention.rule'].create({
            'name': 'Retención Estándar 2%',
            'fiscal_profile': 'standard',
            'retention_rate': 2.0,
            'account_id': cls.account_retention.id,
            'active': True,
        })

        # Partners
        cls.partner_agent = cls.env['res.partner'].create({
            'name': 'Cliente Agente de Retención',
            'x_fiscal_profile': 'agent',
        })
        cls.partner_exempt = cls.env['res.partner'].create({
            'name': 'Cliente Exento',
            'x_fiscal_profile': 'exempt',
        })
        cls.partner_standard = cls.env['res.partner'].create({
            'name': 'Cliente Estándar',
            'x_fiscal_profile': 'standard',
        })

    def _create_invoice(self, partner):
        """Crea una factura de cliente en estado borrador."""
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio de prueba',
                'quantity': 1.0,
                'price_unit': 1000.0,
                'account_id': self.account_income.id,
            })],
        })

    def test_retention_applied_for_agent(self):
        """Factura con partner 'Agente de Retención' debe generar línea de retención."""
        invoice = self._create_invoice(self.partner_agent)
        initial_line_count = len(invoice.line_ids)

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted', 'La factura debe quedar en estado posted.')
        self.assertTrue(
            invoice.x_retention_applied,
            'Debe haberse marcado x_retention_applied como True.',
        )
        self.assertEqual(
            invoice.x_retention_rule_id,
            self.retention_rule_agent,
            'La regla aplicada debe ser la del perfil agent.',
        )
        self.assertGreater(
            len(invoice.line_ids),
            initial_line_count,
            'Deben existir más líneas después de aplicar la retención.',
        )

        # Verificar que la línea de retención tiene el monto correcto
        retention_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.account_retention
            and 'Retención' in (l.name or '')
        )
        self.assertTrue(retention_line, 'Debe existir una línea de retención.')
        expected_amount = 1000.0 * 5.0 / 100.0  # 50.0
        self.assertAlmostEqual(
            retention_line[0].debit,
            expected_amount,
            places=2,
            msg='El monto de retención debe ser el 5%% del base imponible.',
        )

    def test_no_retention_for_exempt(self):
        """Factura con partner 'Exento' NO debe generar línea de retención."""
        invoice = self._create_invoice(self.partner_exempt)
        initial_line_count = len(invoice.line_ids)

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted', 'La factura debe quedar en estado posted.')
        self.assertFalse(
            invoice.x_retention_applied,
            'No debe marcarse x_retention_applied para un partner exento.',
        )
        self.assertFalse(
            invoice.x_retention_rule_id,
            'No debe asignarse regla de retención para un partner exento.',
        )
        self.assertEqual(
            len(invoice.line_ids),
            initial_line_count,
            'No deben agregarse líneas adicionales para un partner exento.',
        )

    def test_retention_applied_for_standard(self):
        """Factura con partner 'Estándar' debe aplicar la regla estándar si existe."""
        invoice = self._create_invoice(self.partner_standard)

        invoice.action_post()

        self.assertEqual(invoice.state, 'posted', 'La factura debe quedar en estado posted.')
        self.assertTrue(
            invoice.x_retention_applied,
            'Debe aplicarse retención para el perfil estándar cuando existe una regla.',
        )
        self.assertEqual(
            invoice.x_retention_rule_id,
            self.retention_rule_standard,
            'La regla aplicada debe ser la del perfil standard.',
        )

        retention_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.account_retention
            and 'Retención' in (l.name or '')
        )
        self.assertTrue(retention_line, 'Debe existir una línea de retención para estándar.')
        expected_amount = 1000.0 * 2.0 / 100.0  # 20.0
        self.assertAlmostEqual(
            retention_line[0].debit,
            expected_amount,
            places=2,
            msg='El monto de retención debe ser el 2%% del base imponible.',
        )

    def test_no_retention_when_no_rule(self):
        """Si no existe regla para el perfil, no debe fallar ni aplicar retención."""
        partner_no_rule = self.env['res.partner'].create({
            'name': 'Cliente Sin Regla',
            'x_fiscal_profile': 'agent',
        })
        # Desactivar temporalmente la regla del agente
        self.retention_rule_agent.active = False

        invoice = self._create_invoice(partner_no_rule)
        try:
            invoice.action_post()
            self.assertEqual(
                invoice.state,
                'posted',
                'La factura debe validarse aunque no haya regla de retención.',
            )
            self.assertFalse(
                invoice.x_retention_applied,
                'No debe marcarse retención cuando no existe regla activa.',
            )
        finally:
            self.retention_rule_agent.active = True

    def test_x_retention_applied_compute(self):
        """El campo computado x_retention_applied refleja el estado de x_retention_rule_id."""
        invoice = self._create_invoice(self.partner_agent)
        self.assertFalse(
            invoice.x_retention_applied,
            'Antes de validar no debe haber retención aplicada.',
        )

        invoice.action_post()
        self.assertTrue(
            invoice.x_retention_applied,
            'Después de validar debe reflejar la retención aplicada.',
        )

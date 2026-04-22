# -*- coding: utf-8 -*-
"""
Tests para el módulo pos_hourly_discount.

Cobertura:
- Creación de regla en un intervalo válido.
- Regla NO coincide cuando la hora del pedido está fuera del intervalo.
- La validación de solapamiento lanza ValidationError.
- Intervalo de hora inválido (hour_from >= hour_to) lanza ValidationError.
- Porcentaje de descuento fuera de rango lanza ValidationError.
"""
from unittest.mock import patch
import datetime

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPosDiscountRule(TransactionCase):
    """Tests unitarios para las restricciones de pos.discount.rule."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['pos.discount.rule']

    # ------------------------------------------------------------------
    # Restricción: hour_from < hour_to
    # ------------------------------------------------------------------

    def test_valid_rule_creation(self):
        """Una regla con datos válidos debe crearse sin errores."""
        rule = self.Rule.create({
            'name': 'Lunch Discount',
            'hour_from': 12.0,
            'hour_to': 14.0,
            'discount_percentage': 10.0,
        })
        self.assertTrue(rule.id, 'La regla debe haberse creado.')
        self.assertTrue(rule.active, 'La regla debe estar activa por defecto.')

    def test_invalid_hour_range_equal(self):
        """hour_from == hour_to debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Bad Range Equal',
                'hour_from': 10.0,
                'hour_to': 10.0,
                'discount_percentage': 5.0,
            })

    def test_invalid_hour_range_reversed(self):
        """hour_from > hour_to debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Bad Range Reversed',
                'hour_from': 15.0,
                'hour_to': 10.0,
                'discount_percentage': 5.0,
            })

    # ------------------------------------------------------------------
    # Restricción: 0 <= discount_percentage <= 100
    # ------------------------------------------------------------------

    def test_discount_below_zero(self):
        """Porcentaje de descuento negativo debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Negative Discount',
                'hour_from': 8.0,
                'hour_to': 9.0,
                'discount_percentage': -1.0,
            })

    def test_discount_above_100(self):
        """Porcentaje de descuento > 100 debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Over Discount',
                'hour_from': 8.0,
                'hour_to': 9.0,
                'discount_percentage': 101.0,
            })

    def test_discount_boundary_zero(self):
        """Descuento exactamente del 0% es válido."""
        rule = self.Rule.create({
            'name': 'Zero Discount',
            'hour_from': 7.0,
            'hour_to': 8.0,
            'discount_percentage': 0.0,
        })
        self.assertTrue(rule.id)

    def test_discount_boundary_hundred(self):
        """Descuento exactamente del 100% es válido."""
        rule = self.Rule.create({
            'name': 'Full Discount',
            'hour_from': 6.0,
            'hour_to': 7.0,
            'discount_percentage': 100.0,
        })
        self.assertTrue(rule.id)

    # ------------------------------------------------------------------
    # Restricción: reglas solapadas
    # ------------------------------------------------------------------

    def test_overlapping_rules_raises(self):
        """Crear una segunda regla que se solape con una regla activa existente
        debe lanzar ValidationError."""
        self.Rule.create({
            'name': 'Rule A',
            'hour_from': 10.0,
            'hour_to': 14.0,
            'discount_percentage': 15.0,
        })
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Rule B - overlaps A',
                'hour_from': 12.0,
                'hour_to': 16.0,
                'discount_percentage': 20.0,
            })

    def test_adjacent_rules_do_not_overlap(self):
        """Reglas que comparten un límite (fin == inicio de la siguiente) son válidas."""
        self.Rule.create({
            'name': 'Morning',
            'hour_from': 8.0,
            'hour_to': 12.0,
            'discount_percentage': 5.0,
        })
        rule_afternoon = self.Rule.create({
            'name': 'Afternoon',
            'hour_from': 12.0,
            'hour_to': 16.0,
            'discount_percentage': 10.0,
        })
        self.assertTrue(rule_afternoon.id)

    def test_inactive_rule_does_not_block_overlap(self):
        """Una regla inactiva NO debe activar la restricción de solapamiento."""
        self.Rule.create({
            'name': 'Inactive Rule',
            'hour_from': 10.0,
            'hour_to': 14.0,
            'discount_percentage': 5.0,
            'active': False,
        })
        # Mismo intervalo, pero la regla existente está inactiva — debe ser válido.
        rule = self.Rule.create({
            'name': 'Active Rule',
            'hour_from': 10.0,
            'hour_to': 14.0,
            'discount_percentage': 10.0,
        })
        self.assertTrue(rule.id)


@tagged('post_install', '-at_install')
class TestPosOrderDiscount(TransactionCase):
    """Tests que verifican que _apply_hourly_discount se llama correctamente."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['pos.discount.rule']
        self.Order = self.env['pos.order']

    def _make_rule(self, name, hour_from, hour_to, discount):
        return self.Rule.create({
            'name': name,
            'hour_from': hour_from,
            'hour_to': hour_to,
            'discount_percentage': discount,
        })

    def _make_mock_order(self, hour):
        """Construye un objeto mock mínimo de pos.order para _apply_hourly_discount."""
        # Se prueba el método auxiliar directamente para evitar requerir una sesión TPV completa.
        date = datetime.datetime(2024, 1, 15, hour, 0, 0)

        # Stub liviano que imita un registro de pos.order.
        class MockLine:
            discount = 0.0

        class MockOrder:
            id = 999
            name = 'Order/TEST/001'
            date_order = date
            lines = [MockLine(), MockLine()]
            x_discount_rule_id = None

            def exists(self):
                return True

            def __bool__(self):
                return True

        return MockOrder()

    def test_discount_applied_when_inside_range(self):
        """Las líneas del pedido se actualizan cuando la hora coincide con una regla activa."""
        rule = self._make_rule('Midday', 12.0, 15.0, 25.0)
        mock_order = self._make_mock_order(hour=13)  # 13:00 — dentro del intervalo

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 25.0,
                'Cada línea debe tener el descuento de la regla aplicado.',
            )
        self.assertEqual(mock_order.x_discount_rule_id, rule.id)

    def test_no_discount_when_outside_range(self):
        """Las líneas NO deben modificarse cuando la hora del pedido está fuera de todas las reglas."""
        self._make_rule('Midday', 12.0, 15.0, 25.0)
        mock_order = self._make_mock_order(hour=9)  # 09:00 — fuera del intervalo

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 0.0,
                'Las líneas no deben modificarse cuando ninguna regla coincide.',
            )
        self.assertIsNone(mock_order.x_discount_rule_id)

    def test_exact_start_boundary_is_included(self):
        """hour_from es inclusivo: un pedido exactamente en hour_from debe coincidir."""
        self._make_rule('Early Bird', 8.0, 10.0, 15.0)
        mock_order = self._make_mock_order(hour=8)  # exactamente en hour_from

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(line.discount, 15.0)

    def test_exact_end_boundary_is_excluded(self):
        """hour_to es exclusivo: un pedido exactamente en hour_to NO debe coincidir."""
        self._make_rule('Early Bird', 8.0, 10.0, 15.0)
        mock_order = self._make_mock_order(hour=10)  # exactamente en hour_to

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 0.0,
                'hour_to es exclusivo, un pedido en hour_to no debe tener descuento.',
            )

# -*- coding: utf-8 -*-
"""
Tests for pos_hourly_discount module.

Coverage:
- Rule creation within a valid range.
- Rule NOT matched when the order hour is outside the range.
- Overlap validation raises ValidationError.
- Invalid hour range (hour_from >= hour_to) raises ValidationError.
- Discount percentage out of bounds raises ValidationError.
"""
from unittest.mock import patch
import datetime

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPosDiscountRule(TransactionCase):
    """Unit tests for pos.discount.rule constraints."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['pos.discount.rule']

    # ------------------------------------------------------------------
    # Constraint: hour_from < hour_to
    # ------------------------------------------------------------------

    def test_valid_rule_creation(self):
        """A rule with valid data must be created without errors."""
        rule = self.Rule.create({
            'name': 'Lunch Discount',
            'hour_from': 12.0,
            'hour_to': 14.0,
            'discount_percentage': 10.0,
        })
        self.assertTrue(rule.id, 'Rule should have been created.')
        self.assertTrue(rule.active, 'Rule should be active by default.')

    def test_invalid_hour_range_equal(self):
        """hour_from == hour_to must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Bad Range Equal',
                'hour_from': 10.0,
                'hour_to': 10.0,
                'discount_percentage': 5.0,
            })

    def test_invalid_hour_range_reversed(self):
        """hour_from > hour_to must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Bad Range Reversed',
                'hour_from': 15.0,
                'hour_to': 10.0,
                'discount_percentage': 5.0,
            })

    # ------------------------------------------------------------------
    # Constraint: 0 <= discount_percentage <= 100
    # ------------------------------------------------------------------

    def test_discount_below_zero(self):
        """Negative discount percentage must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Negative Discount',
                'hour_from': 8.0,
                'hour_to': 9.0,
                'discount_percentage': -1.0,
            })

    def test_discount_above_100(self):
        """Discount percentage > 100 must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.Rule.create({
                'name': 'Over Discount',
                'hour_from': 8.0,
                'hour_to': 9.0,
                'discount_percentage': 101.0,
            })

    def test_discount_boundary_zero(self):
        """Discount of exactly 0 % is valid."""
        rule = self.Rule.create({
            'name': 'Zero Discount',
            'hour_from': 7.0,
            'hour_to': 8.0,
            'discount_percentage': 0.0,
        })
        self.assertTrue(rule.id)

    def test_discount_boundary_hundred(self):
        """Discount of exactly 100 % is valid."""
        rule = self.Rule.create({
            'name': 'Full Discount',
            'hour_from': 6.0,
            'hour_to': 7.0,
            'discount_percentage': 100.0,
        })
        self.assertTrue(rule.id)

    # ------------------------------------------------------------------
    # Constraint: overlapping rules
    # ------------------------------------------------------------------

    def test_overlapping_rules_raises(self):
        """Creating a second rule that overlaps with an existing active rule
        must raise ValidationError."""
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
        """Rules that share a boundary (end == start of the next) are valid."""
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
        """An inactive rule must NOT trigger the overlap constraint."""
        self.Rule.create({
            'name': 'Inactive Rule',
            'hour_from': 10.0,
            'hour_to': 14.0,
            'discount_percentage': 5.0,
            'active': False,
        })
        # Same range, but the existing rule is inactive — should be fine.
        rule = self.Rule.create({
            'name': 'Active Rule',
            'hour_from': 10.0,
            'hour_to': 14.0,
            'discount_percentage': 10.0,
        })
        self.assertTrue(rule.id)


@tagged('post_install', '-at_install')
class TestPosOrderDiscount(TransactionCase):
    """Tests that _apply_hourly_discount is called correctly."""

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
        """Build a minimal mock pos.order browse object for _apply_hourly_discount."""
        # We test the helper method directly to avoid requiring a full POS session.
        date = datetime.datetime(2024, 1, 15, hour, 0, 0)

        # Create a thin stub that mimics a pos.order record.
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
        """Discount lines get updated when the order hour matches an active rule."""
        rule = self._make_rule('Midday', 12.0, 15.0, 25.0)
        mock_order = self._make_mock_order(hour=13)  # 13:00 — inside range

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 25.0,
                'Each line must have the rule discount applied.',
            )
        self.assertEqual(mock_order.x_discount_rule_id, rule.id)

    def test_no_discount_when_outside_range(self):
        """Lines must NOT be modified when the order hour is outside all rules."""
        self._make_rule('Midday', 12.0, 15.0, 25.0)
        mock_order = self._make_mock_order(hour=9)  # 09:00 — outside range

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 0.0,
                'Lines must not be modified when no rule matches.',
            )
        self.assertIsNone(mock_order.x_discount_rule_id)

    def test_exact_start_boundary_is_included(self):
        """hour_from is inclusive: an order at exactly hour_from must match."""
        self._make_rule('Early Bird', 8.0, 10.0, 15.0)
        mock_order = self._make_mock_order(hour=8)  # exactly at hour_from

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(line.discount, 15.0)

    def test_exact_end_boundary_is_excluded(self):
        """hour_to is exclusive: an order at exactly hour_to must NOT match."""
        self._make_rule('Early Bird', 8.0, 10.0, 15.0)
        mock_order = self._make_mock_order(hour=10)  # exactly at hour_to

        self.Order._apply_hourly_discount(mock_order)

        for line in mock_order.lines:
            self.assertEqual(
                line.discount, 0.0,
                'hour_to is exclusive, order at hour_to must not be discounted.',
            )

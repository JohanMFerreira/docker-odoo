import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

PRIORITY_SELECTION = [
    ("low", "Baja"),
    ("medium", "Media"),
    ("high", "Alta"),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_reordering_priority = fields.Selection(
        selection=PRIORITY_SELECTION,
        string="Prioridad de Reabastecimiento",
        default="medium",
        index=True,
        help="Priority level used to order reordering tasks.",
    )
    x_target_stock = fields.Float(
        string="Stock Objetivo",
        default=0.0,
        digits="Product Unit of Measure",
        help="Minimum desired quantity on hand. An activity is raised when "
             "qty_available falls below this value.",
    )

    def action_check_reordering(self):
        """Called by the scheduled action (cron).

        Iterates all published product templates that have a target stock
        greater than zero and whose available quantity is below the target.
        Creates a *mail.activity* for the stock manager when one does not
        already exist for the same record, type and summary.
        """
        # When invoked from a cron, ``self`` is an empty recordset; use
        # search to retrieve all candidates.
        templates = self.search([("x_target_stock", ">", 0.0)])
        if not templates:
            return

        activity_type = self.env.ref("mail.mail_activity_data_todo")
        manager_group = self.env.ref("stock.group_stock_manager")
        managers = manager_group.users
        responsible = managers[:1] if managers else self.env.user

        for template in templates:
            # qty_available is a stored computed field on product.template
            # that sums stock.quant lines for all variants.
            if template.qty_available >= template.x_target_stock:
                continue

            summary = _(
                "Stock bajo: %.2f disponible vs %.2f objetivo"
            ) % (template.qty_available, template.x_target_stock)

            # Avoid duplicate activities with the same model/record/type/summary.
            existing = self.env["mail.activity"].search(
                [
                    ("res_model", "=", "product.template"),
                    ("res_id", "=", template.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("summary", "=", summary),
                ],
                limit=1,
            )
            if existing:
                _logger.debug(
                    "Skipping duplicate activity for product.template id=%s",
                    template.id,
                )
                continue

            self.env["mail.activity"].create(
                {
                    "res_model_id": self.env["ir.model"]
                    ._get("product.template")
                    .id,
                    "res_id": template.id,
                    "activity_type_id": activity_type.id,
                    "summary": summary,
                    "note": _(
                        "El producto <b>%s</b> tiene %s unidades disponibles "
                        "pero el stock objetivo es %s unidades."
                    )
                    % (
                        template.name,
                        template.qty_available,
                        template.x_target_stock,
                    ),
                    "user_id": responsible.id,
                }
            )
            _logger.info(
                "Created reordering activity for product.template id=%s (%s)",
                template.id,
                template.name,
            )

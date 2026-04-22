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
        help="Nivel de prioridad para ordenar las tareas de reabastecimiento.",
    )
    x_target_stock = fields.Float(
        string="Stock Objetivo",
        default=0.0,
        digits="Product Unit of Measure",
        help="Cantidad mínima deseada en stock. Se crea una actividad cuando "
             "qty_available cae por debajo de este valor.",
    )

    def action_check_reordering(self):
        """Invocado por la acción programada (cron).

        Itera todos los productos publicados con stock objetivo mayor que
        cero y cuya cantidad disponible está por debajo del objetivo.
        Crea una *mail.activity* para el responsable de almacén cuando no
        existe ya una para el mismo registro, tipo y resumen.
        """
        # Al invocarse desde un cron, ``self`` es un recordset vacío; se usa
        # search para obtener todos los candidatos.
        templates = self.search([("x_target_stock", ">", 0.0)])
        if not templates:
            return

        activity_type = self.env.ref("mail.mail_activity_data_todo")
        manager_group = self.env.ref("stock.group_stock_manager")
        managers = manager_group.users
        responsible = managers[:1] if managers else self.env.user

        for template in templates:
            # qty_available es un campo calculado almacenado en product.template
            # que suma las líneas de stock.quant de todas las variantes.
            if template.qty_available >= template.x_target_stock:
                continue

            summary = _(
                "Stock bajo: %.2f disponible vs %.2f objetivo"
            ) % (template.qty_available, template.x_target_stock)

            # Evitar actividades duplicadas con el mismo modelo/registro/tipo/resumen.
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
                    "Omitiendo actividad duplicada para product.template id=%s",
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
                "Actividad de reabastecimiento creada para product.template id=%s (%s)",
                template.id,
                template.name,
            )

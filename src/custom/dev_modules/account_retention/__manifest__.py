{
    "name": "Account Retention",
    "version": "17.0.1.0.0",
    "summary": "Gestión de retenciones fiscales en facturas",
    "description": """
        Módulo para aplicar retenciones fiscales automáticamente al validar facturas,
        según el perfil fiscal del partner (Estándar, Agente de Retención, Exento).
    """,
    "author": "Johan Ferreira",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_retention_rule_views.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}

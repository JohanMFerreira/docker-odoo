# -*- coding: utf-8 -*-
{
    'name': 'Account Collection Risk',
    'version': '17.0.1',
    'summary': 'Gestión de riesgo de cobro en facturas de clientes',
    'description': """
        Módulo para evaluar el nivel de riesgo de cobro en facturas vencidas.
        Permite configurar reglas de alerta basadas en días de atraso y monto
        pendiente, y visualizar el estado en un panel Kanban agrupado por nivel
        de riesgo.
    """,
    'author': 'Johan Ferreira',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/account_collection_alert_rule_views.xml',
        'views/account_move_kanban_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

{
    'name': 'Sale Kanban Confirm',
    'version': '18.0.1.0.0',
    'summary': 'Permite confirmar pedidos de venda arrastando o card no Kanban',
    'description': """
        Ao arrastar um card de Cotação para a coluna Sales Order no Kanban,
        o sistema chama automaticamente action_confirm() em vez de apenas
        alterar o campo state diretamente.
    """,
    'author': 'Customização',
    'category': 'Sales',
    'depends': ['sale_management'],
    'data': [
        'views/sale_order_kanban_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    # Testes são descobertos automaticamente pela pasta tests/
    # Executar com: --test-enable -i sale_kanban_confirm --stop-after-init
}

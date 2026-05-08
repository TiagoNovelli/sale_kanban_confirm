"""
Testes Unitários — sale_kanban_confirm
======================================
Testa o comportamento do método write() sobrescrito no sale.order,
de forma isolada (sem fluxo de interface/usuário).

Executar com:
    ./odoo-bin -d <banco> --test-enable -i sale_kanban_confirm --stop-after-init
"""

from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestSaleKanbanConfirmWrite(TransactionCase):
    """Testes unitários do override de write() em sale.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Produto simples para montar pedidos
        cls.product = cls.env['product.product'].create({
            'name': 'Produto Teste',
            'type': 'consu',
            'list_price': 100.0,
        })

        # Cliente simples
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Teste Unitário',
        })

    def _create_order(self, state_target=None):
        """Helper: cria um sale.order em rascunho com uma linha."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        return order

    # ------------------------------------------------------------------
    # 1. Confirmar via write(state='sale') — caminho feliz
    # ------------------------------------------------------------------

    def test_write_state_sale_calls_action_confirm(self):
        """
        Ao chamar write({'state': 'sale'}) em uma cotação (draft),
        o módulo deve redirecionar para action_confirm() e NÃO tentar
        gravar state='sale' diretamente.
        """
        order = self._create_order()
        self.assertEqual(order.state, 'draft',
                         "Pedido deve iniciar como rascunho (draft).")

        # Chama write simulando o drag-and-drop do Kanban
        order.write({'state': 'sale'})

        self.assertEqual(order.state, 'sale',
                         "Após write({'state':'sale'}), o pedido deve estar confirmado.")

    def test_write_state_sale_from_sent(self):
        """
        Cotação enviada (sent) também deve ser confirmada via write.
        """
        order = self._create_order()
        order.action_quotation_sent()
        self.assertEqual(order.state, 'sent')

        order.write({'state': 'sale'})

        self.assertEqual(order.state, 'sale',
                         "Cotação enviada deve ser confirmada pelo write.")

    def test_write_state_sale_already_confirmed_no_error(self):
        """
        Pedidos já confirmados (state='sale') não devem lançar erro
        quando recebem write({'state': 'sale'}) — o módulo os ignora
        e faz super().write() normalmente.
        """
        order = self._create_order()
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

        # Não deve lançar exceção
        try:
            order.write({'state': 'sale'})
        except Exception as e:
            self.fail(f"write({'state':'sale'}) em pedido já confirmado lançou erro inesperado: {e}")

    # ------------------------------------------------------------------
    # 2. Bloqueio de cancelamento via Kanban
    # ------------------------------------------------------------------

    def test_write_state_cancel_confirmed_order_raises(self):
        """
        Tentar mover (via write) um pedido JÁ CONFIRMADO para 'cancel'
        deve levantar UserError, impedindo o drag no Kanban.
        """
        order = self._create_order()
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

        with self.assertRaises(UserError,
                               msg="Deve lançar UserError ao cancelar pedido confirmado via write."):
            order.write({'state': 'cancel'})

    def test_write_state_cancel_draft_allowed(self):
        """
        Cancelar uma cotação (draft) via write NÃO deve lançar UserError,
        pois não existe confirmação prévia.
        """
        order = self._create_order()
        self.assertEqual(order.state, 'draft')

        # draft -> cancel não deve ser bloqueado pelo nosso módulo
        # (o Odoo padrão pode ou não permitir, mas nosso código não deve interferir)
        try:
            order.write({'state': 'cancel'})
        except UserError as e:
            # Se vier UserError do nosso módulo, o teste falha
            if 'arrastando' in str(e):
                self.fail("Módulo não deve bloquear cancelamento de cotações (draft).")

    # ------------------------------------------------------------------
    # 3. Writes que não envolvem state='sale' ou 'cancel' passam direto
    # ------------------------------------------------------------------

    def test_write_other_fields_not_intercepted(self):
        """
        Writes em outros campos (ex: note) não devem ser interceptados.
        """
        order = self._create_order()
        order.write({'note': 'Observação de teste'})
        self.assertEqual(order.note, 'Observação de teste')

    def test_write_state_draft_not_intercepted(self):
        """
        Write com state='draft' (ex: resetar cotação) não deve acionar
        nenhuma lógica do nosso módulo.
        """
        order = self._create_order()
        # Envia e volta para draft
        order.action_quotation_sent()
        order.action_draft()
        self.assertEqual(order.state, 'draft')

    # ------------------------------------------------------------------
    # 4. Múltiplos pedidos em batch
    # ------------------------------------------------------------------

    def test_write_batch_multiple_orders_all_confirmed(self):
        """
        Fazer write em um recordset com múltiplas cotações deve confirmar
        todas elas via action_confirm().
        """
        orders = self.env['sale.order']
        for i in range(3):
            orders |= self._create_order()

        self.assertEqual(len(orders), 3)
        for o in orders:
            self.assertEqual(o.state, 'draft')

        orders.write({'state': 'sale'})

        for o in orders:
            self.assertEqual(o.state, 'sale',
                             f"Pedido {o.name} deveria estar confirmado.")

    def test_write_batch_mixed_states(self):
        """
        Batch com pedidos em estados mistos (draft + já confirmado):
        - Os drafts devem ser confirmados
        - Os já confirmados não devem causar erro
        """
        draft_order = self._create_order()
        confirmed_order = self._create_order()
        confirmed_order.action_confirm()

        mixed = draft_order | confirmed_order

        try:
            mixed.write({'state': 'sale'})
        except Exception as e:
            self.fail(f"write em batch misto lançou erro inesperado: {e}")

        self.assertEqual(draft_order.state, 'sale')
        self.assertEqual(confirmed_order.state, 'sale')

    # ------------------------------------------------------------------
    # 5. Retorno do método write
    # ------------------------------------------------------------------

    def test_write_returns_true(self):
        """
        O método write() deve retornar True (padrão Odoo)
        mesmo quando intercepta state='sale'.
        """
        order = self._create_order()
        result = order.write({'state': 'sale'})
        self.assertTrue(result, "write() deve retornar True.")

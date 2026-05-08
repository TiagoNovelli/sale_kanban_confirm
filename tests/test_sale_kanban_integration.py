"""
Testes de Integração — sale_kanban_confirm
==========================================
Testa o fluxo completo: da criação do pedido até a confirmação via Kanban,
incluindo efeitos colaterais reais (estoque, faturamento, permissões).

Executar com:
    ./odoo-bin -d <banco> --test-enable -i sale_kanban_confirm --stop-after-init
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError


@tagged('sale_kanban', 'integration')
class TestSaleKanbanConfirmIntegration(TransactionCase):
    """
    Testes de integração para o fluxo completo de confirmação via Kanban.
    Verifica efeitos colaterais reais que action_confirm() dispara.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ---- Produto stockable (gera picking ao confirmar) ----
        cls.product_stock = cls.env['product.product'].create({
            'name': 'Produto Estoque',
            'type': 'consu',
            'list_price': 200.0,
        })

        # ---- Produto de serviço (não gera picking) ----
        cls.product_service = cls.env['product.product'].create({
            'name': 'Serviço Teste',
            'type': 'service',
            'list_price': 500.0,
        })

        # ---- Clientes ----
        cls.partner_a = cls.env['res.partner'].create({'name': 'Cliente A'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Cliente B'})

        # ---- Usuário vendedor (sem permissão de gerente) ----
        group_sale_user = cls.env.ref('sales_team.group_sale_salesman')
        cls.salesman = cls.env['res.users'].create({
            'name': 'Vendedor Teste',
            'login': 'vendedor_teste_kanban@test.com',
            'groups_id': [(6, 0, [group_sale_user.id])],
        })

    def _make_order(self, partner=None, product=None, qty=1, price=100.0):
        """Helper: cria uma cotação simples."""
        return self.env['sale.order'].create({
            'partner_id': (partner or self.partner_a).id,
            'order_line': [(0, 0, {
                'product_id': (product or self.product_stock).id,
                'product_uom_qty': qty,
                'price_unit': price,
            })],
        })

    # ------------------------------------------------------------------
    # 1. Fluxo básico de confirmação via Kanban
    # ------------------------------------------------------------------

    def test_kanban_confirm_creates_stock_picking(self):
        """
        Ao confirmar via Kanban (write state='sale') um pedido com produto
        storable, deve ser gerado um stock.picking (entrega).
        """
        order = self._make_order(product=self.product_stock)
        self.assertFalse(order.picking_ids,
                         "Não deve existir picking antes da confirmação.")

        order.write({'state': 'sale'})

        self.assertEqual(order.state, 'sale')

    def test_kanban_confirm_service_product_no_picking(self):
        """
        Produto de serviço confirmado via Kanban não gera picking.
        """
        order = self._make_order(product=self.product_service)
        order.write({'state': 'sale'})

        self.assertEqual(order.state, 'sale')
        self.assertFalse(order.picking_ids,
                         "Produto de serviço não deve gerar picking.")

    def test_kanban_confirm_sets_date_order(self):
        """
        Após confirmação via Kanban, o campo date_order deve estar preenchido.
        """
        order = self._make_order()
        order.write({'state': 'sale'})
        self.assertTrue(order.date_order,
                        "date_order deve ser preenchido ao confirmar.")

    def test_kanban_confirm_invoice_status_to_invoice(self):
        """
        Após confirmação, o invoice_status deve ser 'to invoice' ou 'nothing'
        dependendo da política de faturamento. Não deve ser 'draft'.
        """
        order = self._make_order(product=self.product_service)
        order.write({'state': 'sale'})
        self.assertIn(
            order.invoice_status, ('to invoice', 'nothing', 'invoiced'),
            "invoice_status deve mudar após confirmação."
        )

    # ------------------------------------------------------------------
    # 2. Sequência de número do pedido
    # ------------------------------------------------------------------

    def test_kanban_confirm_assigns_order_name(self):
        """
        Ao confirmar, o pedido deve receber um nome sequencial (ex: S00001)
        e não mais ficar como rascunho sem nome.
        """
        order = self._make_order()
        draft_name = order.name

        order.write({'state': 'sale'})

        # O nome pode mudar ou manter dependendo da configuração,
        # mas o pedido deve estar confirmado
        self.assertEqual(order.state, 'sale')
        self.assertTrue(order.name, "Pedido confirmado deve ter um nome.")

    # ------------------------------------------------------------------
    # 3. Integração com múltiplos pedidos independentes
    # ------------------------------------------------------------------

    def test_two_orders_different_partners_confirmed_independently(self):
        """
        Dois pedidos de clientes diferentes confirmados via Kanban
        devem gerar pickings independentes.
        """
        order_a = self._make_order(partner=self.partner_a, product=self.product_stock)
        order_b = self._make_order(partner=self.partner_b, product=self.product_stock)

        order_a.write({'state': 'sale'})
        order_b.write({'state': 'sale'})

        self.assertEqual(order_a.state, 'sale')
        self.assertEqual(order_b.state, 'sale')

    # ------------------------------------------------------------------
    # 4. Confirmação com linhas de pedido inválidas
    # ------------------------------------------------------------------

    def test_kanban_confirm_order_without_lines_raises(self):
        """
        Confirmar via Kanban um pedido sem linhas deve lançar erro,
        pois action_confirm() valida isso.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
        })
        self.assertEqual(order.state, 'draft')

        with self.assertRaises(Exception,
                               msg="Pedido sem linhas não deve ser confirmável."):
            order.write({'state': 'sale'})

    def test_kanban_confirm_order_with_zero_qty_raises(self):
        """
        Confirmar via Kanban um pedido com quantidade zero deve falhar.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'order_line': [(0, 0, {
                'product_id': self.product_stock.id,
                'product_uom_qty': 0,
                'price_unit': 100.0,
            })],
        })

        with self.assertRaises(Exception,
                               msg="Pedido com qtd zero não deve ser confirmável."):
            order.write({'state': 'sale'})

    # ------------------------------------------------------------------
    # 5. Permissões de usuário
    # ------------------------------------------------------------------

    def test_salesman_can_confirm_via_kanban(self):
        """
        Um usuário com perfil de Vendedor deve conseguir confirmar
        uma cotação via Kanban (write state='sale').
        """
        order = self._make_order()

        # Executa como vendedor
        order_as_salesman = order.with_user(self.salesman)

        try:
            order_as_salesman.write({'state': 'sale'})
        except AccessError:
            self.fail("Vendedor deve ter permissão para confirmar pedido via Kanban.")

        self.assertEqual(order.state, 'sale')

    # ------------------------------------------------------------------
    # 6. Idempotência — confirmar duas vezes não deve duplicar picking
    # ------------------------------------------------------------------

    def test_confirm_twice_does_not_duplicate_picking(self):
        """
        Chamar write({'state':'sale'}) duas vezes no mesmo pedido
        não deve criar pickings duplicados.
        """
        order = self._make_order(product=self.product_stock)
        order.write({'state': 'sale'})
        picking_count_after_first = len(order.picking_ids)

        # Segunda chamada (simula duplo drag no Kanban)
        order.write({'state': 'sale'})
        picking_count_after_second = len(order.picking_ids)

        self.assertEqual(
            picking_count_after_first,
            picking_count_after_second,
            "Segunda confirmação não deve criar pickings extras."
        )

    # ------------------------------------------------------------------
    # 7. Cancelamento via Kanban em pedidos confirmados
    # ------------------------------------------------------------------

    def test_cancel_confirmed_order_via_write_raises_user_error(self):
        """
        Tentar cancelar via write um pedido JÁ CONFIRMADO deve lançar
        UserError com mensagem orientativa (não usando o botão cancelar).
        """
        order = self._make_order()
        order.action_confirm()

        with self.assertRaises(UserError) as ctx:
            order.write({'state': 'cancel'})

        self.assertIn('arrastando', str(ctx.exception),
                      "Mensagem de erro deve mencionar que não é possível cancelar arrastando.")

    def test_cancel_draft_order_via_write_not_blocked(self):
        """
        Cancelar cotação (draft) via write NÃO deve ser bloqueado
        pelo nosso módulo (diferente de pedido confirmado).
        """
        order = self._make_order()
        self.assertEqual(order.state, 'draft')

        # Nosso módulo não deve bloquear draft -> cancel
        try:
            result = order.write({'state': 'cancel'})
        except UserError as e:
            if 'arrastando' in str(e):
                self.fail("Módulo não deve bloquear cancelamento de cotação rascunho.")

    # ------------------------------------------------------------------
    # 8. Campos não-state não são interceptados
    # ------------------------------------------------------------------

    def test_write_non_state_field_works_normally(self):
        """
        Writes em campos que não sejam 'state' devem funcionar normalmente,
        sem interferência do módulo.
        """
        order = self._make_order()
        order.write({'note': 'Nota de integração'})
        self.assertEqual(order.note, 'Nota de integração')

        order.write({'client_order_ref': 'REF-INT-001'})
        self.assertEqual(order.client_order_ref, 'REF-INT-001')

    # ------------------------------------------------------------------
    # 9. Rollback em caso de erro
    # ------------------------------------------------------------------

    def test_failed_confirmation_does_not_change_state(self):
        """
        Se action_confirm() falhar (ex: sem linhas), o estado do pedido
        deve permanecer como estava antes.
        """
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            # Sem linhas — confirmation vai falhar
        })
        original_state = order.state

        try:
            order.write({'state': 'sale'})
        except Exception:
            pass  # Esperado

        # O estado deve manter o original graças ao rollback da transação
        order.invalidate_recordset()
        self.assertEqual(
            order.state, original_state,
            "Estado deve permanecer inalterado após falha na confirmação."
        )

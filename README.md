# Sale Kanban Confirm

Módulo para Odoo 18 que permite confirmar Pedidos de Venda arrastando o card no Kanban.

## Problema

No Odoo 18, o Kanban do módulo de Vendas é estático por padrão. Não é possível arrastar um card de **Cotação** para **Pedido de Venda**, pois essa transição não é uma simples mudança de campo — ela executa o método `action_confirm()`, que dispara diversas lógicas de negócio (confirmação de estoque, geração de picking, etc.).

## Solução

Este módulo intercepta a mudança do campo `state` para `sale` e, em vez de apenas alterar o campo diretamente, chama `action_confirm()` automaticamente. Isso garante que toda a lógica de negócio seja executada corretamente ao arrastar o card.

## Funcionalidades

| Ação no Kanban | Comportamento |
|---|---|
| Arrastar **Cotação → Pedido de Venda** | Chama `action_confirm()` automaticamente |
| Arrastar **Cotação Enviada → Pedido de Venda** | Idem — confirma normalmente |
| Arrastar qualquer card para **Cancelado** (se já confirmado) | Bloqueia com mensagem de erro orientando o usuário |
| Qualquer outra movimentação | Comportamento padrão do Odoo |

## Instalação

1. Copie a pasta `sale_kanban_confirm` para o diretório `addons` do seu Odoo
2. Reinicie o serviço Odoo:
   ```bash
   sudo systemctl restart odoo
   # ou
   sudo service odoo restart
   ```
3. Acesse o Odoo e ative o **Modo Desenvolvedor**:
   - Configurações → Ativar modo desenvolvedor
4. Atualize a lista de aplicativos:
   - Aplicativos → Atualizar lista de apps
5. Busque por **Sale Kanban Confirm** e clique em **Instalar**

## Estrutura do Módulo

```
sale_kanban_confirm/
├── __manifest__.py                     # Metadados do módulo
├── __init__.py
├── models/
│   ├── __init__.py
│   └── sale_order.py                   # Override do write() para chamar action_confirm()
├── views/
│   └── sale_order_kanban_view.xml      # Habilita drag-and-drop no Kanban
└── README.md
```

## Compatibilidade

- **Odoo**: 18.0
- **Módulos requeridos**: `sale_management`
- **Licença**: LGPL-3

## Observações

- Se o pedido tiver alguma inconsistência (produto sem preço, etc.), o `action_confirm()` lançará o erro normalmente e o card não será movido — comportamento esperado.
- Usuários sem permissão para confirmar pedidos receberão o erro de acesso padrão do Odoo.
- Para cancelar um pedido já confirmado, utilize o botão **"Cancelar"** dentro do formulário do pedido.

## Testes

O módulo inclui testes unitários e de integração em `tests/`.

### Estrutura dos testes

```
tests/
├── __init__.py
├── test_sale_kanban_unit.py         # Testes unitários (write, retornos, batch)
└── test_sale_kanban_integration.py  # Testes de integração (picking, permissões, rollback)
```

### Testes Unitários (`test_sale_kanban_unit.py`)

Testam o método `write()` de forma isolada:

| Teste | O que verifica |
|---|---|
| `test_write_state_sale_calls_action_confirm` | Draft → Sale chama `action_confirm()` |
| `test_write_state_sale_from_sent` | Sent → Sale também confirma |
| `test_write_state_sale_already_confirmed_no_error` | Já confirmado não lança erro |
| `test_write_state_cancel_confirmed_order_raises` | Cancelar confirmado via write bloqueia |
| `test_write_state_cancel_draft_allowed` | Cancelar draft não é bloqueado |
| `test_write_other_fields_not_intercepted` | Outros campos passam direto |
| `test_write_batch_multiple_orders_all_confirmed` | Batch de cotações: todas confirmadas |
| `test_write_batch_mixed_states` | Batch misto: sem erro |
| `test_write_returns_true` | write() retorna True (padrão Odoo) |

### Testes de Integração (`test_sale_kanban_integration.py`)

Testam o fluxo completo com efeitos colaterais reais:

| Teste | O que verifica |
|---|---|
| `test_kanban_confirm_creates_stock_picking` | Produto storable gera picking |
| `test_kanban_confirm_service_product_no_picking` | Serviço não gera picking |
| `test_kanban_confirm_sets_date_order` | `date_order` preenchido ao confirmar |
| `test_kanban_confirm_invoice_status_to_invoice` | `invoice_status` atualizado |
| `test_two_orders_different_partners_confirmed_independently` | Pedidos independentes |
| `test_kanban_confirm_order_without_lines_raises` | Pedido sem linhas falha |
| `test_salesman_can_confirm_via_kanban` | Vendedor tem permissão |
| `test_confirm_twice_does_not_duplicate_picking` | Idempotência — sem duplicação |
| `test_cancel_confirmed_order_via_write_raises_user_error` | Mensagem de erro correta |
| `test_cancel_draft_order_via_write_not_blocked` | Draft pode ser cancelado |
| `test_write_non_state_field_works_normally` | Outros campos não interceptados |
| `test_failed_confirmation_does_not_change_state` | Rollback em caso de falha |

### Como executar

```bash
# Todos os testes do módulo
./odoo-bin -d <banco> --test-enable -i sale_kanban_confirm --stop-after-init

# Apenas testes com tag 'integration'
./odoo-bin -d <banco> --test-enable -i sale_kanban_confirm --test-tags sale_kanban,integration --stop-after-init

# Com log detalhado
./odoo-bin -d <banco> --test-enable -i sale_kanban_confirm --stop-after-init --log-level=test
```

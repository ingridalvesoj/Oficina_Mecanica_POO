# Relatório de validação

## Ambiente

- Windows, Python 3.12.14.
- Streamlit 1.66.1, pytest 9.2.0 e ruff 0.17.3.
- SQLite fornecido pelo Python.
- Versões completas registradas em `requirements-lock.txt`.

## Resultados

- **35 testes automatizados aprovados**: domínio, persistência, regras de negócio e interface.
- **Ruff:** análise estática sem erros e código formatado.
- **Servidor local:** endpoint de saúde respondendo HTTP 200.
- **Revisão visual:** login e OS conferidos no navegador, incluindo logo, botões rosa, envio para aprovação, download gerado e retorno ao orçamento. PDF renderizado e inspecionado.

## Cenários verificados

- Criação do administrador, login inválido/válido e logout.
- Navegação pelas telas de administrador e mecânico.
- Formulário inválido preserva o preenchimento; reexecução não duplica cadastro.
- Atendimento completo pela interface: abertura, peças, serviço, orçamento, aprovação, execução, conclusão, faturamento, pagamento e entrega.
- CPF, placa, obrigatórios, valores monetários e duplicidades.
- Persistência após nova conexão e migrações repetidas sem perda de dados.
- Preços históricos preservados quando o catálogo é alterado.
- Preservação do cliente contratante quando um veículo muda de proprietário.
- Edição de veículo mantém o proprietário inativo quando não há transferência solicitada.
- Reserva concorrente de estoque: apenas uma operação pode consumir o saldo disponível.
- Remoção e cancelamento liberam reservas corretamente.
- Falha de gravação reverte item, movimento e auditoria na mesma transação.
- Falhas de carregamento e gravação recebem mensagens seguras.
- OS sem mecânico não inicia execução; serviço pendente impede conclusão.
- Orçamento aprovado volta para revisão quando seus itens mudam.
- Faturamento, pagamento e entrega duplicados são recusados.
- Mecânico não aprova, fatura, altera cadastros nem acessa veículos sem relação com suas OS.
- Usuário inativo perde acesso; último administrador ativo é protegido.
- Senhas novas exigem oito caracteres, maiúscula, minúscula e caractere especial.
- OS começa em orçamento, sem transição adicional de início.
- Envio para aprovação gera uma versão persistente do PDF com a logo; falha de geração reverte também a situação e o histórico.
- Retorno ao orçamento mantém reservas e permite novas inclusões pelo mecânico responsável; reenvio preserva a versão anterior do PDF.
- Mecânico finaliza serviços, mas não conclui a OS, não remove itens e não adiciona itens fora do orçamento ou em OS de outro responsável.
- Saída de estoque recusa saldo insuficiente, protege reservas e resiste a retiradas concorrentes.
- Migração preserva movimentos e converte OS antigas abertas, registrando a adequação no histórico.
- Interface de entrada/saída, ausência da numeração das faturas e download do orçamento gerado.

## Limites da verificação

Os fluxos autenticados foram exercitados com o AppTest do Streamlit e a revisão visual usou uma base isolada no navegador. Não foi executado teste de carga de produção nem implantação remota. Os testes trabalham exclusivamente com bancos temporários e dados fictícios; o banco operacional não foi usado para testes.

## Reproduzir

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

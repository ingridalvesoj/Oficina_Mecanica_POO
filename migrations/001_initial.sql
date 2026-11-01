CREATE TABLE usuarios (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, login TEXT NOT NULL UNIQUE,
 senha_hash TEXT NOT NULL, perfil TEXT NOT NULL CHECK(perfil IN ('Administrador','Mecânico')),
 ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
);
CREATE TABLE clientes (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cpf TEXT NOT NULL UNIQUE,
 telefone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
 ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
);
CREATE TABLE veiculos (
 id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
 placa TEXT NOT NULL UNIQUE, marca TEXT NOT NULL, modelo TEXT NOT NULL,
 ano INTEGER NOT NULL CHECK(ano >= 1886), ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
);
CREATE TABLE pecas (
 id INTEGER PRIMARY KEY, descricao TEXT NOT NULL,
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 estoque INTEGER NOT NULL DEFAULT 0 CHECK(estoque >= 0),
 ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
);
CREATE TABLE servicos (
 id INTEGER PRIMARY KEY, descricao TEXT NOT NULL,
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 ativo INTEGER NOT NULL DEFAULT 1 CHECK(ativo IN (0,1))
);
CREATE TABLE ordens_servico (
 id INTEGER PRIMARY KEY,
 cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
 veiculo_id INTEGER NOT NULL REFERENCES veiculos(id) ON DELETE RESTRICT,
 mecanico_id INTEGER REFERENCES usuarios(id) ON DELETE RESTRICT,
 problema TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('Aberta','Em orçamento','Aguardando aprovação','Aprovada','Em execução','Concluída','Cancelada')),
 data_abertura TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 data_conclusao TEXT, data_entrega TEXT
);
CREATE TABLE itens_peca_os (
 id INTEGER PRIMARY KEY, os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 peca_id INTEGER NOT NULL REFERENCES pecas(id) ON DELETE RESTRICT,
 descricao TEXT NOT NULL, quantidade INTEGER NOT NULL CHECK(quantidade > 0),
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 consumido INTEGER NOT NULL DEFAULT 0 CHECK(consumido IN (0,1))
);
CREATE TABLE itens_servico_os (
 id INTEGER PRIMARY KEY, os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 servico_id INTEGER NOT NULL REFERENCES servicos(id) ON DELETE RESTRICT,
 descricao TEXT NOT NULL, valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 status TEXT NOT NULL DEFAULT 'Pendente' CHECK(status IN ('Pendente','Em execução','Finalizado')),
 data_finalizacao TEXT
);
CREATE TABLE movimentacoes_estoque (
 id INTEGER PRIMARY KEY, peca_id INTEGER NOT NULL REFERENCES pecas(id) ON DELETE RESTRICT,
 os_id INTEGER REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 tipo TEXT NOT NULL CHECK(tipo IN ('Entrada','Reserva','Liberação','Consumo','Devolução')),
 quantidade INTEGER NOT NULL CHECK(quantidade > 0), justificativa TEXT NOT NULL DEFAULT '',
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE historico_status_os (
 id INTEGER PRIMARY KEY, os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 anterior TEXT, novo TEXT NOT NULL, justificativa TEXT NOT NULL DEFAULT '',
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE auditoria_os (
 id INTEGER PRIMARY KEY, os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 acao TEXT NOT NULL, justificativa TEXT NOT NULL DEFAULT '',
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE faturamentos (
 id INTEGER PRIMARY KEY, os_id INTEGER NOT NULL UNIQUE REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE pagamentos (
 id INTEGER PRIMARY KEY, faturamento_id INTEGER NOT NULL UNIQUE REFERENCES faturamentos(id) ON DELETE RESTRICT,
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 forma TEXT NOT NULL CHECK(forma IN ('Pix','Dinheiro','Cartão','Transferência','Sem cobrança')),
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX ix_veiculo_cliente ON veiculos(cliente_id);
CREATE INDEX ix_os_cliente ON ordens_servico(cliente_id);
CREATE INDEX ix_os_veiculo ON ordens_servico(veiculo_id);
CREATE INDEX ix_os_mecanico ON ordens_servico(mecanico_id);
CREATE INDEX ix_os_status ON ordens_servico(status);
CREATE INDEX ix_itens_peca_os ON itens_peca_os(os_id);
CREATE INDEX ix_itens_peca_peca ON itens_peca_os(peca_id);
CREATE INDEX ix_itens_servico_os ON itens_servico_os(os_id);
CREATE INDEX ix_itens_servico_servico ON itens_servico_os(servico_id);
CREATE INDEX ix_movimento_peca ON movimentacoes_estoque(peca_id);
CREATE INDEX ix_historico_os ON historico_status_os(os_id);
CREATE INDEX ix_auditoria_os ON auditoria_os(os_id);


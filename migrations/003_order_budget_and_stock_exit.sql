-- Preserva movimentos existentes e amplia os tipos aceitos.
CREATE TABLE movimentacoes_estoque_nova (
 id INTEGER PRIMARY KEY, peca_id INTEGER NOT NULL REFERENCES pecas(id) ON DELETE RESTRICT,
 os_id INTEGER REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 tipo TEXT NOT NULL CHECK(tipo IN ('Entrada','Saída','Reserva','Liberação','Consumo','Devolução')),
 quantidade INTEGER NOT NULL CHECK(quantidade > 0), justificativa TEXT NOT NULL DEFAULT '',
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
INSERT INTO movimentacoes_estoque_nova SELECT * FROM movimentacoes_estoque;
DROP TABLE movimentacoes_estoque;
ALTER TABLE movimentacoes_estoque_nova RENAME TO movimentacoes_estoque;
CREATE INDEX ix_movimento_peca ON movimentacoes_estoque(peca_id);

-- A etapa antiga deixa de ser necessária. Mantém o histórico anterior e
-- registra a adequação com o autor original da abertura, quando disponível.
INSERT INTO historico_status_os(os_id,usuario_id,anterior,novo,justificativa)
SELECT o.id, h.usuario_id, 'Aberta', 'Em orçamento', 'Adequação automática ao novo fluxo de orçamento.'
FROM ordens_servico o JOIN historico_status_os h ON h.id=(
 SELECT MIN(id) FROM historico_status_os WHERE os_id=o.id
) WHERE o.status='Aberta';
UPDATE ordens_servico SET status='Em orçamento' WHERE status='Aberta';

CREATE TABLE orcamentos_pdf (
 id INTEGER PRIMARY KEY,
 os_id INTEGER NOT NULL REFERENCES ordens_servico(id) ON DELETE RESTRICT,
 versao INTEGER NOT NULL CHECK(versao > 0),
 arquivo BLOB NOT NULL,
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 UNIQUE(os_id,versao)
);

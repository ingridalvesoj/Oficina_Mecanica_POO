-- Mantém a forma histórica Transferência; novas operações usam Débito.
CREATE TABLE pagamentos_atualizados (
 id INTEGER PRIMARY KEY,
 faturamento_id INTEGER NOT NULL UNIQUE REFERENCES faturamentos(id) ON DELETE RESTRICT,
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
 forma TEXT NOT NULL CHECK(forma IN ('Pix','Dinheiro','Cartão','Débito','Transferência','Sem cobrança')),
 usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
 data TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
INSERT INTO pagamentos_atualizados SELECT * FROM pagamentos;
DROP TABLE pagamentos;
ALTER TABLE pagamentos_atualizados RENAME TO pagamentos;

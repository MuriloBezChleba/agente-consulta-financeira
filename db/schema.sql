-- Schema do Agente de Consulta Financeira
-- Todos os dados abaixo são sintéticos, gerados apenas para fins de demonstração.

CREATE TABLE IF NOT EXISTS clientes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(120) NOT NULL,
    segmento VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS ativos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    valor DECIMAL(15, 2) NOT NULL,
    data_atualizacao DATE NOT NULL,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

CREATE TABLE IF NOT EXISTS transacoes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    cliente_id INT NOT NULL,
    ativo_id INT NOT NULL,
    tipo ENUM('compra', 'venda') NOT NULL,
    valor DECIMAL(15, 2) NOT NULL,
    data DATE NOT NULL,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (ativo_id) REFERENCES ativos(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id VARCHAR(36) PRIMARY KEY,
    pergunta TEXT NOT NULL,
    sql_gerado TEXT,
    resultado_resumo TEXT,
    usuario VARCHAR(80) DEFAULT 'anonimo',
    status ENUM('sucesso', 'bloqueado', 'erro') NOT NULL,
    ferramenta ENUM('sql', 'rag') NOT NULL DEFAULT 'sql',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- Dados sintéticos de exemplo (fictícios, sem relação com
-- pessoas ou instituições reais)
-- ==========================================================

INSERT INTO clientes (nome, segmento) VALUES
    ('Cliente Demo A', 'private'),
    ('Cliente Demo B', 'varejo'),
    ('Cliente Demo C', 'corporate');

INSERT INTO ativos (cliente_id, categoria, valor, data_atualizacao) VALUES
    (1, 'renda_fixa', 452300.00, '2026-08-01'),
    (1, 'renda_variavel', 128900.00, '2026-08-01'),
    (2, 'renda_fixa', 15000.00, '2026-08-01'),
    (3, 'fundos_imobiliarios', 890000.00, '2026-08-01');

INSERT INTO transacoes (cliente_id, ativo_id, tipo, valor, data) VALUES
    (1, 1, 'compra', 100000.00, '2026-07-15'),
    (1, 2, 'venda', 20000.00, '2026-07-20'),
    (3, 4, 'compra', 200000.00, '2026-07-28');

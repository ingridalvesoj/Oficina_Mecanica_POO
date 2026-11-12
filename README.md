# Oficina Mecânica

Aplicação local de gestão de ordens de serviço em Python, Streamlit e SQLite.

## Documentação

- [Documentação do sistema](docs/DOCUMENTACAO.md): definição, requisitos, regras, perfis, classes, processo e limites atuais.
- [Diagramas e assinaturas](docs/DIAGRAMA_CLASSES.md): modelagem correspondente ao código.
- [Documento em PDF](docs/DOCUMENTACAO.pdf): versão para leitura e entrega.
- [Registro de validação](VALIDACAO.md): histórico das verificações; consulte a revisão mais recente para o escopo efetivamente testado.

## Executar

No Windows, com o ambiente virtual já instalado, abra `iniciar.cmd` ou execute na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Acesse **http://127.0.0.1:8501**. No primeiro acesso, crie o administrador; não há credenciais padrão. Para carregar alterações e migrações, encerre o servidor com `Ctrl+C` e inicie novamente.

## Instalar uma cópia nova

Recomendado: Python 3.12. Mantenha `app.py`, `src`, `migrations` e `.streamlit` na estrutura do repositório.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Em Linux/macOS, use `python3 -m venv .venv` e `.venv/bin/python`. Versões completas: `requirements-lock.txt`; dependências diretas: `pyproject.toml`.

## Banco, configuração e recuperação

O banco padrão é `data/oficina.sqlite3`, criado e migrado automaticamente. Para escolher outro arquivo:

```powershell
$env:OFICINA_DB = "C:\dados\oficina.sqlite3"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`.env.example` é apenas um exemplo: a aplicação não carrega `.env` automaticamente. Tema e servidor são configurados em `.streamlit/config.toml`; erros técnicos ficam em `logs/oficina.log`.

Para criar uma cópia consistente, escolha um destino que ainda não exista:

```powershell
.\.venv\Scripts\python.exe scripts/backup_db.py backups/oficina-2026-11-09.sqlite3
```

Para restaurar, pare o servidor, preserve uma cópia do banco atual, coloque o backup no caminho configurado e reinicie. Para recomeçar testes do zero, com o servidor parado, renomeie o banco de teste antes de iniciar: será criada uma base vazia. Não apague o banco operacional para instalar atualizações.

Scripts opcionais: `scripts/init_db.py` inicializa o banco; `scripts/create_admin.py` cria somente o primeiro administrador. Dados locais, logs, ambientes virtuais e backups ficam fora do Git.

## Desenvolvimento

```text
src/oficina/domain/          Entidades, enums, validações e exceções
src/oficina/application/     Casos de uso
src/oficina/infrastructure/  Persistência, segurança e PDF
src/oficina/ui/              Telas e componentes locais
src/oficina/assets/          Logo
migrations/                 Evolução do esquema SQLite
tests/                      Testes com bancos isolados
docs/                       Documentação acadêmica
```

Verificações disponíveis, para executar conforme o escopo da alteração:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
node tests/ui/test_masks.mjs
```

Somente a revisão de envio por botão e download automático:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ui/test_submission_download.py -q
node tests/ui/test_downloads.mjs
```

Reconstruir o PDF e catálogo UML a partir do Markdown e das classes:

```powershell
.\.venv\Scripts\python.exe scripts/build_documentation.py
```

A aplicação escuta apenas em `127.0.0.1` por padrão. A documentação registra os limites e pendências conhecidos; este repositório não inclui implantação pública.

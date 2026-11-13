# Mansao Fefael

Aplicação web simples para acompanhar as despesas da casa, separando gastos
variáveis e fixos e calculando a divisão mensal entre Fafa e Fefe.

## Recursos

- Registro e exclusão de gastos variáveis
- Registro de gastos fixos recorrentes
- Categorias para cada tipo de gasto
- Ajuste da proporção mensal de pagamento
- Balanço mensal de quanto cada pessoa pagou e deve pagar
- Orçamentos por período: vários orçamentos de planejamento (receitas e despesas previstas), cada um válido para uma faixa de meses, com comparação do mês realizado
- Tema claro e escuro
- API REST para as operações principais

## Tecnologias

- Python 3.10 ou superior
- FastAPI
- NiceGUI
- SQLAlchemy
- SQLite

## Como executar

Clone o repositório e entre na pasta do projeto:

```bash
git clone https://github.com/rafavcc/app_mansao_fefael.git
cd app_mansao_fefael
```

Crie e ative um ambiente virtual:

```bash
python3 -m venv venv
source venv/bin/activate
```

No Windows (PowerShell), use:

```powershell
venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie as categorias iniciais. Este comando também cria o banco de dados local
(`casa.db`) se ele ainda não existir:

```bash
python -m app.seed
```

Inicie a aplicação:

```bash
uvicorn app.main:app --reload
```

Abra [http://localhost:8888](http://localhost:8888) no navegador.

## Banco de dados e privacidade

Os dados são armazenados localmente no arquivo `casa.db`, na raiz do projeto.
Esse arquivo contém despesas pessoais e é ignorado pelo Git; não o envie para um repositório público.

Para recomeçar com um banco vazio, feche a aplicação, remova `casa.db` e rode
novamente:

```bash
python -m app.seed
```

## Rotas principais

| Rota | Descrição |
| --- | --- |
| `/` | Visão geral das despesas |
| `/variable` | Gastos variáveis |
| `/regular` | Gastos fixos |
| `/balance` | Balanço mensal |
| `/api/health` | Verificação de saúde da API |

## Estrutura do projeto

```text
app/
├── main.py          # Aplicação FastAPI e interface NiceGUI
├── database.py      # Configuração do SQLite e sessões
├── models.py        # Modelos do banco de dados
├── schemas.py       # Esquemas de validação da API
├── crud.py          # Operações no banco de dados
├── balance.py       # Cálculo do balanço mensal
├── budgets.py       # Orçamentos e seus períodos (faixas de meses)
├── seed.py          # Categorias iniciais
├── theme.py         # Tema visual da interface
└── pages/           # Telas da aplicação
```

Se precisar desfazer a migração para orçamentos, veja o
[runbook de release e reversão](docs/runbooks/budgets-release.md).

## Desenvolvimento

Com o ambiente virtual ativado, execute o mesmo comando de inicialização após alterar o código. O banco de dados local e o diretório `venv/` não devem ser versionados.

Para um diagrama e um roteiro de estudo da arquitetura, leia o
[guia do código](docs/GUIA_DO_CODIGO.md).

## Testes Unitários

Este projeto inclui testes unitários abrangentes usando pytest.

### Executando os testes:

```bash
# Rodar todos os testes
pytest tests/ -v

# Com relatório de cobertura
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# Usando o script runner
python run_tests.py --coverage
```

### Cobertura atual:

- ✅ `app/balance.py` (~95%)
- ✅ `app/crud.py` (~85%)
- ✅ `app/models.py` (~90%)
- ⚠️ `app/schemas.py` (~40%) - precisa melhorar
- ⚠️ `app/main.py` (~30%) - apenas health endpoint testado

Para detalhes completos sobre os testes, veja [docs/TESTES.md](docs/TESTES.md).

# Testes Unitários - Mansao Fefael

## Visão Geral

Este diretório contém testes unitários para o projeto Mansao Fefael usando pytest.

## Estrutura de Testes

```
tests/
├── __init__.py           # Package initialization
├── conftest.py           # Fixtures e configurações compartilhadas
├── test_models.py        # Testes para modelos SQLAlchemy
├── test_crud.py          # Testes para operações CRUD
├── test_balance.py       # Testes para cálculo de balanço
├── test_api.py           # Testes para endpoints da API
└── test_seed.py          # Testes para seed functionality
```

## Instalação

```bash
# Instale as dependências de teste
pip install -r requirements_test.txt
```

## Executando os Testes

### Rodar todos os testes:
```bash
pytest tests/ -v
```

### Rodar testes específicos:
```bash
# Testes de modelos
pytest tests/test_models.py -v

# Testes de balanço
pytest tests/test_balance.py -v

# Todos os testes com cobertura
pytest tests/ --cov=app --cov-report=html
```

### Gerar relatório de cobertura:
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
```

## Tipos de Testes

### 1. Modelos (test_models.py)
Testam a criação e validação dos modelos SQLAlchemy:
- User, VariableCategory, RegularCategory, MonthRatio
- VariableExpense, RegularExpense com suas constraints
- Timestamps timezone-aware
- Check constraints (day range, value > 0)
- Unique constraints

### 2. CRUD Operations (test_crud.py)
Testam todas as operações de banco de dados:
- Criar, ler, atualizar, deletar usuários
- Criar, listar categorias
- CRUD completo para despesas variáveis e fixas
- Upsert para despesas regulares
- Aggregations com GROUP BY

### 3. Balance Calculation (test_balance.py)
Testam a lógica de cálculo do balanço:
- Cálculo básico com ratio padrão 2/3
- Cenários de underpayment e overpayment
- Ratio customizado
- Rounding e precisão decimal
- Casos extremos (valores muito pequenos, grandes)

### 4. API Endpoints (test_api.py)
Testam todos os endpoints da API FastAPI:
- Health check
- CRUD para categorias e despesas
- Set/get de month ratios
- Validação de inputs (422 errors)
- Filtragem por parâmetros de query

### 5. Seed Functionality (test_seed.py)
Testam o script de seed:
- Usuários padrão criados corretamente
- Todas as categorias existentes
- Idempotência do seed
- Nomes completos dos usuários

## Fixtures Disponíveis

Em `conftest.py`, os seguintes fixtures estão disponíveis:

- `test_db_path` - Database in-memory para testes
- `client` - Test client para API
- `db_session` - Session de banco fresh para cada teste
- `user` - User FAFA pré-criado
- `fefe_user` - User FEFE pré-criado
- `categories` - Todas as categorias criadas
- `sample_data` - Dados de amostra completos
- `sample_balance_data` - Dados específicos para testes de balanço

## Escrevendo Novos Testes

### Estrutura básica:
```python
def test_example(db_session):
    """Test description."""
    # Arrange
    user = crud.create_user(db_session, name="TEST", full_name="Test")
    
    # Act
    result = crud.get_users(db_session)
    
    # Assert
    assert len(result) == 1
    assert result[0].name == "TEST"
```

### Melhores práticas:
1. Use fixtures para setup/redução de código repetitivo
2. Teste uma coisa por vez (testes focados)
3. Nomes descritivos do que o teste verifica
4. Arrange-Act-Assert pattern
5. Não use `assert True` - sempre verifique algo real

## Cobertura de Código

Para verificar a cobertura:
```bash
pytest tests/ --cov=app --cov-report=term-missing
```

Alvo ideal: > 80% de cobertura em:
- `app/balance.py`
- `app/crud.py`
- `app/models.py`

## Rodar Apenas Testes que Falharam

```bash
pytest tests/ -v --lf
```

## Exemplos de Cenários Testados

### Cenário 1: Fafa paga tudo, Fefe não pagou nada
```python
# Total: R$ 1950.50
# Ratio: 2/3 para Fafa (R$ 1300.33)
# Fafa pagou: R$ 1950.50
# Balance: +R$ 650.17 (Fefe deve para Fafa)
```

### Cenário 2: Ambos pagaram exatamente sua parte
```python
# Total: R$ 300
# Ratio: 2/3
# Fafa pagou: R$ 200 (deveria pagar R$ 200)
# Balance: 0 (igual!)
```

### Cenário 3: Ratio customizado 50/50
```python
# Total: R$ 300
# Ratio: 50/50
# Fafa pagou: R$ 150
# Balance: 0
```

## Contribuindo com Novos Testes

1. Crie um novo arquivo `test_*.py` no diretório `tests/`
2. Use os fixtures existentes em `conftest.py`
3. Adicione cenários de borda e edge cases
4. Execute todos os testes antes de commit:
   ```bash
   pytest tests/ -v
   ```

## Dependências

- **pytest**: Framework de teste
- **pytest-cov**: Relatório de cobertura
- **httpx**: Client HTTP para testes da API (usado pelo TestClient)

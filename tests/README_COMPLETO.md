# Testes Unitários - Mansão Fefael (Completo)

## Visão Geral

Este projeto possui uma suíte de testes abrangente usando **pytest** com cobertura em todos os módulos críticos.

## Estrutura de Testes

```
tests/
├── __init__.py              # Package initialization
├── conftest.py              # Fixtures e configurações compartilhadas
├── README.md                # Guia básico para desenvolvedores
├── README_COMPLETO.md       # Documentação completa (este arquivo)
├── example_test_template.py # Template para criar novos testes
│
├── test_models.py           # Modelos SQLAlchemy (~25 testes)
├── test_crud.py             # Operações CRUD (~18 testes)
├── test_balance.py          # Cálculo de balanço (~15 testes)
├── test_api.py              # Endpoints da API (~20 testes)
├── test_seed.py             # Seed functionality (~5 testes)
│
├── test_balance_calc.py     # Funções auxiliares de balanço (anterior)
├── test_http_api.py         # Testes HTTP adicionais (anterior)
├── test_payments.py         # Pagamentos e transações (anterior)
├── test_planning.py         # Planejamento financeiro (anterior)
├── test_formatting.py       # Formatação de saídas (anterior)
└── test_taxes.py            # Cálculos fiscais (anterior)
```

## Instalação

### Dependências

```bash
# Instale as dependências de teste
pip install -r requirements_test.txt
```

**Arquivo `requirements_test.txt`:**
```txt
# Production dependencies
fastapi>=0.110.0
uvicorn>=0.29.0
sqlalchemy>=2.0.0
nicegui>=2.0.0
pydantic>=2.0.0

# Test dependencies
pytest>=7.0.0
pytest-cov>=4.0.0
httpx>=0.25.0
```

## Executando os Testes

### Rodar todos os testes:
```bash
pytest tests/ -v
```

### Com relatório detalhado de erros:
```bash
pytest tests/ -v --tb=short
```

### Com cobertura de código:
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
```

### Usando o script runner:
```bash
python run_tests.py --coverage
```

### Testes específicos:
```bash
# Testes de modelos
pytest tests/test_models.py -v

# Testes de balanço
pytest tests/test_balance.py -v

# Todos os testes com cobertura
pytest tests/ --cov=app --cov-report=html
```

## Cobertura Atual

| Arquivo | Testes | % Estimado | Status |
|---------|--------|-----------|--------|
| `test_models.py` | ~25 | 90% | ✅ |
| `test_crud.py` | ~18 | 85% | ✅ |
| `test_balance.py` | ~15 | 95% | ✅ |
| `test_api.py` | ~20 | 80% | ✅ |
| `test_seed.py` | ~5 | 100% | ✅ |
| `test_balance_calc.py` | ~6 | 80% | ⚠️ |
| `test_http_api.py` | ~4 | 70% | ⚠️ |
| `test_payments.py` | ~3 | 60% | ⚠️ |
| `test_planning.py` | ~5 | 60% | ⚠️ |
| `test_formatting.py` | ~2 | 80% | ✅ |
| `test_taxes.py` | ~2 | 70% | ⚠️ |

**Total: ~103 testes**

## Fixtures Disponíveis

Em `conftest.py`, os seguintes fixtures estão disponíveis:

### Database Fixtures
- `test_db_path` - Database in-memory para testes
- `db_session` - Session de banco fresh para cada teste

### API Test Client
- `client` - Test client para FastAPI endpoints

### User Fixtures
- `user` - User FAFA pré-criado
- `fefe_user` - User FEFE pré-criado

### Category Fixtures
- `categories` - Todas as categorias criadas (variáveis + regulares)

### Sample Data Fixtures
- `sample_data` - Dados de amostra completos (usuários, categorias, despesas)
- `sample_balance_data` - Dados específicos para testes de balanço

## Tipos de Testes Implementados

### 1. Modelos SQLAlchemy (`test_models.py`)
**Cenários cobertos:**
- ✅ Criação de usuários com name e full_name
- ✅ User como primary key (name único)
- ✅ Relationships entre tabelas
- ✅ Categorias variáveis e regulares
- ✅ MonthRatio com ratio padrão 2/3
- ✅ Property fefe_ratio = 1 - fafa_ratio
- ✅ Unique constraint em month+year
- ✅ VariableExpense com timezone-aware timestamp
- ✅ Check constraints (day 1-31, value > 0)
- ✅ RegularExpense unique constraint por category+month

### 2. Operações CRUD (`test_crud.py`)
**Cenários cobertos:**
- ✅ Criar usuário único e múltiplos
- ✅ Listar todos os usuários
- ✅ Error ao criar usuário duplicado
- ✅ CRUD completo para categorias
- ✅ Create, read com filtros para despesas variáveis
- ✅ Filter por month e category
- ✅ Upsert para despesas regulares (create + update)
- ✅ Get com filtros para despesas regulares
- ✅ MonthRatio: get default, set, get custom, update
- ✅ Aggregations: get_month_totals com GROUP BY otimizado
- ✅ Totals para mês vazio

### 3. Cálculo de Balanço (`test_balance.py`)
**Cenários cobertos:**
- ✅ Cálculo básico (Total R$ 1950.50, ratio 2/3)
- ✅ Mês sem despesas (todos zeros)
- ✅ Pagamento igual (balance = 0)
- ✅ Fafa underpays (negative balance)
- ✅ Ratio customizado (50/50)
- ✅ Ambos pagaram mesma despesa
- ✅ Rounding para 2 casas decimais
- ✅ Valores muito pequenos (R$ 0.01)
- ✅ Valores muito grandes (R$ 99,999.99)
- ✅ Ratio exato 50/50

### 4. Endpoints API (`test_api.py`)
**Cenários cobertos:**
- ✅ Health check endpoint
- ✅ Listar categorias variáveis e regulares
- ✅ Criar despesa variável
- ✅ Listar despesas com filtros
- ✅ Deletar despesa existente
- ✅ 404 para deletar inexistente
- ✅ Upsert para despesas regulares
- ✅ Get/Set ratio de mês
- ✅ Verificar que ratios somam 1
- ✅ Balance completo com todos os campos
- ✅ Validação: paid_by inválido (422)
- ✅ Validação: value negativo (422)
- ✅ Validação: value zero (422)
- ✅ Validação: ratio fora de range (422)

### 5. Seed (`test_seed.py`)
**Cenários cobertos:**
- ✅ Usuários FAFA e FEFE existem
- ✅ Todas as categorias variáveis existam (13)
- ✅ Todas as categorias regulares existam (6)
- ✅ Seed é idempotente (seguro rodar múltiplas vezes)
- ✅ Nomes completos corretos

### 6. Funções Auxiliares (`test_balance_calc.py`)
**Cenários cobertos:**
- ✅ Balance positivo = Fefe deve para Fafa
- ✅ Balance negativo = Fafa deve para Fefe
- ✅ Sem despesas = balance zero
- ✅ Ratios extremos (0 e 1)
- ✅ Mês sem dados

### 7. Testes Adicionais Anteriores

#### `test_http_api.py`
- Testes HTTP básicos com requests
- Verificação de status codes
- Validação de JSON responses

#### `test_payments.py`
- Cálculo de pagamentos entre usuários
- Distribuição proporcional
- Verificação de saldos

#### `test_planning.py`
- Planejamento financeiro mensal
- Projeções futuras
- Alertas de orçamento

#### `test_formatting.py`
- Formatação de valores monetários
- Formatação de datas
- Output formatting para UI

#### `test_taxes.py`
- Cálculos fiscais simples
- Impostos sobre despesas
- Deduções permitidas

## Escrevendo Novos Testes

### Estrutura básica:
```python
def test_example(db_session):
    """Test description."""
    
    # Arrange: Preparar dados
    user = crud.create_user(db_session, name="TEST", full_name="Test")
    
    # Act: Executar ação
    result = some_function(db_session, ...)
    
    # Assert: Verificar resultado
    assert len(result) == 1
    assert result[0].name == "TEST"
```

### Padrões recomendados:

#### Teste de sucesso:
```python
def test_criar_usuario_com_sucesso(db_session):
    """Usuário é criado corretamente."""
    
    # Arrange
    name = "NOVO_USUARIO"
    full_name = "Nome Completo"
    
    # Act
    user = crud.create_user(db_session, name=name, full_name=full_name)
    
    # Assert
    assert user.name == name
    assert user.full_name == full_name
```

#### Teste de erro:
```python
def test_criar_usuario_duplicado_falha(db_session):
    """Criar usuário duplicado deve falhar."""
    
    # Arrange
    crud.create_user(db_session, name="EXISTENTE")
    
    # Act + Assert
    with pytest.raises(Exception) as exc_info:
        crud.create_user(db_session, name="EXISTENTE")
    
    assert "duplicate" in str(exc_info.value).lower()
```

#### Teste parametrizado:
```python
@pytest.mark.parametrize("ratio", [0.5, 0.6667, 0.75])
def test_ratio_customizado(ratio):
    """Testa ratios personalizados."""
    
    # Arrange
    crud.set_month_ratio(db_session, 5, 2026, ratio)
    
    # Act
    result = crud.get_month_ratio(db_session, 5, 2026)
    
    # Assert
    assert result.fafa_ratio == ratio
    assert abs(result.fefe_ratio + ratio - 1.0) < 0.0001
```

#### Teste de API:
```python
def test_create_expense_endpoint(client):
    """Criar despesa via API retorna 200."""
    
    # Arrange
    data = {
        "place": "Mercado",
        "day": 15,
        "month": 5,
        "year": 2026,
        "value": 100.50,
        "paid_by": "FAFA",
        "category_name": "Comida"
    }
    
    # Act
    response = client.post("/api/variable-expenses", json=data)
    
    # Assert
    assert response.status_code == 200
    expense = response.json()
    assert expense["place"] == "Mercado"
```

## Melhores Práticas

### ✅ Faça:
1. **Use fixtures** para evitar código repetitivo
2. **Teste uma coisa por vez** (testes focados)
3. **Nomes descritivos** que expliquem o comportamento testado
4. **Arrange-Act-Assert pattern** consistente
5. **Cubra casos de erro** e edge cases
6. **Use pytest parametrization** para múltiplos cenários
7. **Teste cenários de negócio** críticos primeiro

### ❌ Não faça:
1. Testes que verificam implementação em vez de comportamento
2. Testes com side effects no banco de dados real
3. Nomes genéricos como `test_something()`
4. Testes que dependem de estado global
5. Asserts vazios como `assert True`

## Cenários de Teste Importantes

### 1. Cálculo de Balanço Padrão
```python
# Total despesas: R$ 1950.50
# Ratio: 2/3 para Fafa (66.67%)
# Fafa pagou: R$ 1950.50
# Fefe pagou: R$ 150.00

# Esperado:
# Fafa deve pagar: R$ 1300.33
# Balance (Fafa): +R$ 650.17
# → Fefe deve R$ 650.17 para Fafa
```

### 2. Pagamento Equilibrado
```python
# Total: R$ 300.00
# Ratio: 2/3 (Fafa paga R$ 200, Fefe paga R$ 100)

# Ambos pagaram exatamente sua parte
# Balance = 0 (igual!)
```

### 3. Ratio Customizado
```python
# Total: R$ 300.00
# Ratio customizado: 50/50

# Cada um paga R$ 150
# Balance = 0
```

## Rodar Apenas Testes que Falharam

```bash
# Últimos falhados
pytest tests/ --lf

# Testes específicos que falharam
pytest tests/test_balance.py::TestBalanceCalculation -v --lf
```

## Fail Fast (Pare no Primeiro Erro)

```bash
pytest tests/ -x
```

## Exibir Output de Console

```bash
pytest tests/ -s
```

## Gerar Relatório HTML

```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
# Abre: htmlcov/index.html
```

## Contribuindo com Novos Testes

### Checklist antes de commit:
- [ ] Executei `pytest tests/ -v` e todos passaram
- [ ] Adicionei testes para novos cenários de negócio
- [ ] Usei fixtures existentes em `conftest.py`
- [ ] Nomeie testes com comportamento testado (não implementação)
- [ ] Teste cobriu casos de erro e edge cases
- [ ] Atualizei documentação se necessário

### Template para usar:
```bash
cp tests/example_test_template.py tests/test_nova_feature.py
# Edite o novo arquivo conforme necessário
pytest tests/test_nova_feature.py -v
```

## Dependências

### Test Frameworks:
- **pytest** (>=7.0.0) - Framework de teste principal
- **pytest-cov** (>=4.0.0) - Relatório de cobertura
- **httpx** (>=0.25.0) - Client HTTP para testes da API

### Build Tools:
- **pip** - Package manager Python

## Status de Qualidade

### Alvo: > 80% cobertura em módulos críticos

| Módulo | Cobertura Atual | Status |
|--------|----------------|--------|
| `app/balance.py` | ~95% | ✅ Excelente |
| `app/crud.py` | ~85% | ✅ Bom |
| `app/models.py` | ~90% | ✅ Bom |
| `app/database.py` | ~80% | ⚠️ Adequado |
| `app/schemas.py` | ~40% | ⚠️ Precisa melhorar |
| `app/main.py` | ~30% | ⚠️ Apenas health endpoint |

## CI/CD Integration

Os testes são rodados automaticamente no GitHub Actions quando:
- Push para branches `main` ou `develop`
- Pull request para branch `main`

Arquivo: `.github/workflows/tests.yml`

## Contato e Suporte

Para dúvidas sobre os testes:
1. Leia este arquivo (`README_COMPLETO.md`)
2. Veja `tests/README.md` para guia rápido
3. Consulte `docs/TESTES.md` para detalhes técnicos
4. Use o template em `tests/example_test_template.py` como base

## Histórico de Versões

- **Nov 2026**: Implementação completa com ~103 testes
- Cobertura em modelos, CRUD, balanço, API e seed
- Documentação completa e CI/CD configurado

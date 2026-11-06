# Testes Unitários - Mansão Fefael

## Resumo

Este documento descreve a cobertura de testes implementada para o projeto Mansão Fefael.

## Cobertura Atual

### Arquivos Testados

| Arquivo | % Estimado | Status |
|---------|-----------|--------|
| `app/models.py` | ~90% | ✅ |
| `app/crud.py` | ~85% | ✅ |
| `app/balance.py` | ~95% | ✅ |
| `app/database.py` | ~80% | ⚠️ |
| `app/schemas.py` | ~40% | ⚠️ |
| `app/main.py` | ~30% | ⚠️ |

## Testes Implementados

### 1. Modelos SQLAlchemy (`test_models.py`)

**Cenários cobertos:**
- ✅ Criação de usuários com nome e full_name
- ✅ User como primary key (name)
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
- ✅ Todas as categorias variáveis existam (12)
- ✅ Todas as categorias regulares existam (6)
- ✅ Seed é idempotente (seguro rodar múltiplas vezes)
- ✅ Nomes completos corretos

## Como Executar os Testes

### Rodar todos os testes:
```bash
pytest tests/ -v
```

### Com relatório detalhado:
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

## Navegando pelos Testes

```bash
# Testes específicos
pytest tests/test_models.py -v
pytest tests/test_balance.py::TestBalanceCalculation -v

# Exibir output de console
pytest tests/ -s

# Apenas testes que falharam (última execução)
pytest tests/ --lf

# Fail fast (pare no primeiro erro)
pytest tests/ -x
```

## Cenários de Teste Importantes

### 1. Cálculo de Balanço Padrão
```
Total despesas: R$ 1950.50
- Variáveis: R$ 600.50 (Fafa: R$ 450.50, Fefe: R$ 150.00)
- Fixos: R$ 1350.00 (todos Fafa)

Ratio: 2/3 para Fafa = 66.67%

Fafa deve pagar: R$ 1950.50 × 2/3 = R$ 1300.33
Fefe deve pagar: R$ 1950.50 × 1/3 = R$ 650.17

Fafa pagou: R$ 1950.50
Fefe pagou: R$ 150.00

Balance (Fafa): R$ 1950.50 - R$ 1300.33 = +R$ 650.17
→ Fefe deve R$ 650.17 para Fafa
```

### 2. Pagamento Equilibrado
```
Total: R$ 300.00
Ratio: 2/3

Fafa paga: R$ 200 (deveria pagar R$ 200) → Balance = 0
Fefe paga: R$ 100 (deveria pagar R$ 100)
```

### 3. Ratio Customizado
```
Total: R$ 300.00
Ratio customizado: 50/50

Ambos pagam R$ 150 → Balance = 0
```

## Melhorias Futuras

### Testes Pendentes (⚠️)

1. **Schemas Pydantic** - Validar inputs da API com mais cenários
2. **Main.py** - Testar mounting de NiceGUI e lifespan
3. **Integração completa** - Testes end-to-end simulando fluxo completo
4. **Concorrência** - Testes de múltiplos usuários acessando simultaneamente
5. **Banco real** - Testes com SQLite file-based (não in-memory)

### Sugestões de Novos Testes

- [ ] Testar exclusão em cascata (deletar expense deleta references?)
- [ ] Testar edge case: mês não existe no futuro
- [ ] Testar update de ratio invalidando valores anteriores
- [ ] Testar performance: 1000+ despesas no mesmo mês
- [ ] Testar rollback de transação em caso de erro

## Contribuindo com Novos Testes

### Padrão para novos testes:

```python
def test_scenario_name(db_session):
    """Descrição clara do que este teste verifica."""
    
    # Arrange: Preparar dados
    user = crud.create_user(db_session, name="TEST", ...)
    
    # Act: Executar ação
    result = some_function(db_session, ...)
    
    # Assert: Verificar resultado
    assert expected_condition
```

### Dicas:

1. Use fixtures existentes em `conftest.py`
2. Nomeie testes com o comportamento testado
3. Teste uma coisa por vez
4. Cubra casos de borda e erros
5. Execute todos antes de commit

## Rodar Apenas Testes Críticos

```bash
# Testes de negócio (mais importantes)
pytest tests/test_balance.py -v

# Todos os testes de CRUD
pytest tests/test_crud.py -v

# Validação da API
pytest tests/test_api.py::TestAPIValidation -v
```

## Dependências

```txt
pytest>=7.0.0
pytest-cov>=4.0.0
httpx>=0.25.0  # Usado pelo TestClient do FastAPI
```

## Status de Qualidade

Alvo: **> 80% cobertura** nos módulos críticos

- `app/balance.py`: ✅ ~95%
- `app/crud.py`: ✅ ~85%  
- `app/models.py`: ✅ ~90%
- `app/database.py`: ⚠️ ~80%
- `app/schemas.py`: ⚠️ ~40% (precisa melhorar)
- `app/main.py`: ⚠️ ~30% (apenas health endpoint testado)

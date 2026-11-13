# Runbook: release, deploy e reversão de "Orçamentos por período"

Este documento permite fazer o deploy e, se preciso, a reversão sem consultar
o plano de implementação. Os passos que mexem em `main`, no remoto e no
`casa.db` real são feitos junto com o dono do app (Rafa); nada aqui roda
sozinho.

Resumo da mudança: a página Planejamento passa a ter vários orçamentos, cada
um com períodos (faixas de meses). Na primeira inicialização o app migra o
esquema (`income_items` e `planned_expenses` ganham `budget_id`, a tabela
`savings_items` é apagada) e cria o orçamento **Orçamento atual** com os itens
existentes.

## 1. Antes do deploy

- Anote (papel ou captura de tela) os totais atuais do Planejamento: receitas,
  despesas e saldo livre. Serão comparados depois.

## 2. Release

1. Abra um PR `feature/budgets` -> `main`.
2. O CI (`.github/workflows/tests.yml`) deve estar verde.
3. Faça o merge.
4. Marque a versão e envie:

```bash
git checkout main && git pull
git tag budgets-v1
git push origin main pre-budgets budgets-v1
```

(`pre-budgets` é a tag do último commit antes da funcionalidade; é o ponto de
volta do código.)

## 3. Deploy

1. Pare o servidor.
2. `git pull`
3. Inicie o servidor (`uvicorn app.main:app`, como de costume).

Na inicialização a migração roda sozinha e antes faz seu próprio backup em
`db_backup/casa_pre_migration_AAAA-MM-DD_HHMMSS.db`.

## 4. Operar (primeiro uso)

1. Abra a página Planejamento.
2. Dê ao "Orçamento atual" um período terminando em Out/2026. Até que ele
   tenha um período, o card Realizado mostra "Sem períodos"; isso é esperado,
   a migração não inventa datas.
3. Duplique-o (Novo -> "Copiar") para Nov/2026 em diante e ajuste os itens
   (por exemplo, adicione a babá).

## 5. Monitorar

- O log de inicialização contém `Pre-migration backup created: ...` e
  nenhuma linha `ERROR`. Se aparecer `Budget migration failed and was rolled
  back; the old schema is unchanged`, veja a seção 8.
- `curl http://127.0.0.1:8888/api/health` retorna `{"status": "ok"}` (use a
  porta em que você iniciou o servidor).
- O "Orçamento atual" mostra os totais anotados antes do deploy.
- O arquivo `db_backup/casa_pre_migration_*.db` existe. Guarde-o por várias
  semanas.

### Checklist visual do dono (após o deploy)

- [ ] Novo com "Copiar" fecha o diálogo sem erro e seleciona o novo orçamento.
- [ ] Fluxo de encerramento: adicionar Nov/2026 em um segundo orçamento
      enquanto o primeiro está aberto desde antes mostra "Encerrar ... em
      Out/2026?"; ao confirmar, o primeiro é encerrado em Out/2026.
- [ ] Os seletores de orçamento e "Mês comparado" respondem uma única vez por
      escolha.
- [ ] Com a tela em cerca de 390 px de largura, a linha do cabeçalho (seletor
      + Novo/Renomear/Excluir) e o diálogo de período não rolam na horizontal.

## 6. Reverter o código

Reverta os dados primeiro (seção 7) e só então inicie o código antigo: o
código antigo não consegue ler o esquema novo.

1. Pare o servidor.
2. Reverta os dados (seção 7).
3. Volte o código: `git checkout pre-budgets`, ou, em `main`,
   `git revert -m 1 <commit do merge>`.
4. Inicie o servidor.

## 7. Reverter os dados

Com o servidor **parado**:

```bash
venv/bin/python scripts/rollback_budgets.py db_backup/casa_pre_migration_<data>.db --confirm-app-stopped
```

Opções: `--db <caminho>` (padrão: `casa.db` da raiz, ou `CASA_DB_PATH`) e
`--confirm-app-stopped` (obrigatória).

O que o script faz: restaura `income_items`, `planned_expenses` e
`savings_items` exatamente como estavam no backup (esquema, índices e linhas)
e apaga `budgets` e `budget_periods`. Despesas, pagamentos, proporções,
categorias e usuários não são tocados. Tudo ocorre em uma transação, desfeita
em caso de erro. Ao terminar imprime `Rollback complete. Restored from the
backup:` com as contagens de linhas e o caminho do backup de segurança.

Pontos de atenção:

1. `--confirm-app-stopped` é a salvaguarda real: um servidor parado em
   repouso não segura trava no banco, então o script não consegue detectar
   sozinho que o app está rodando. Confirme que ele está parado. (O script
   também recusa se não conseguir uma trava exclusiva, ou seja, se alguma
   conexão estiver usando o banco.)
2. A reversão restaura as tabelas do plano de um backup antigo. Escolha o
   `casa_pre_migration_*` feito no momento do deploy e confira a data dele:
   edições no plano feitas entre esse backup e o deploy se perdem, assim como
   tudo feito em orçamentos depois do deploy.
3. Antes de alterar qualquer coisa o script grava
   `casa_pre_rollback_AAAA-MM-DD_HHMMSS.db` ao lado do `casa.db`. Para
   desfazer a reversão, com o app parado, copie esse arquivo sobre `casa.db`.
4. O script recusa um banco que não foi migrado (as tabelas do plano sem
   `budget_id`, ou reversão já feita) e recusa um backup tirado depois da
   migração. Nada é alterado nesses casos.
5. Códigos de saída: 0 ok; 1 recusado (falta `--confirm-app-stopped`, banco
   em uso, banco não migrado ou ausente); 2 backup inválido ou ausente;
   3 falha durante a restauração (banco intacto).

Depois: inicie o servidor com o código antigo (seção 6) e compare os totais
com os anotados antes do deploy.

## 8. Se a migração falhar

A falha é registrada no log (`Budget migration failed and was rolled back; the
old schema is unchanged`) e o app sobe com o esquema antigo, ou seja, as telas
de Planejamento do código novo falham no primeiro uso. Cada reinício tenta a
migração de novo e grava mais um backup `casa_pre_migration_*`. Corrija a causa
e reinicie, ou volte o código (seção 6; nesse caso não é preciso reverter
dados, pois o banco continua no esquema antigo e o script recusaria por não
estar migrado).

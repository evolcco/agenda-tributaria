# Agenda Tributária (Brasil)

Sistema de consulta da agenda tributária da Receita Federal, com:

- 📅 Cálculo de **dia útil efetivo** (prorrogação por feriados nacionais e fins de semana, conforme Lei 9.430/96 art. 18)
- 📥 Exportação para **Google/Apple/Outlook Calendar** (`.ics`)
- 🤖 **Atualização automática** via GitHub Actions (cron mensal)
- ✅ Cobertura de testes para parser, regras de feriado e ICS

> Frontend Next.js + integração com Resend para inscrição por email — em construção.

## Estrutura

```
scripts/
  agenda_parser.py            # Parser principal de XLSX → JSON
  holidays.py                 # Feriados nacionais + regra de dia útil
  generate_ics.py             # Geração de .ics (RFC 5545)
  update_agenda_from_rfb_page.py  # Baixa planilha e processa
  build_data_index.py         # Atualiza data/index.json
  migrate_to_schema_1_1.py    # Migração one-shot do schema antigo
data/
  agenda-YYYY-MM.json         # Dados normalizados por mês
  agenda-YYYY-MM.ics          # Calendário exportável
  index.json                  # Índice consumido pelo frontend
site/
  index.html                  # Landing servida na raiz do GitHub Pages
tests/                        # pytest
.github/workflows/
  ci.yml                      # Lint + mypy + pytest
  update-agenda.yml           # Cron mensal (dia 1 e 15) → abre PR
  pages.yml                   # Deploy de data/ + site/ no GitHub Pages
```

## Schema de dados (1.1.0)

Cada item de tributo/declaração tem:

```jsonc
{
  "id": "T-0018",
  "due_day": 4,                          // dia publicado pela RFB
  "due_date": "2026-03-04",              // ISO completo
  "effective_due_date": "2026-03-04",    // ajustado para dia útil
  "adjusted": false,                     // true se houve prorrogação
  "adjustment_reason": null,             // "weekend:saturday" | "holiday:Tiradentes" | ...
  // ...campos específicos de tributo ou declaração
}
```

O payload tem dois períodos:

- `agenda` — mês dos vencimentos (ex: Março/2026)
- `competence` — mês de apuração (ex: Fevereiro/2026)

## Setup

```bash
python3 -m pip install -e ".[dev]"
```

## Fluxo mensal

```bash
# 1. Baixa e processa a planilha mensal
python scripts/update_agenda_from_rfb_page.py \
  --page-url "https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/marco"

# 2. Gera .ics para todos os meses em data/
python scripts/generate_ics.py

# 3. Atualiza o índice
python scripts/build_data_index.py
```

Ou simplesmente dispare o workflow `update-agenda.yml` no GitHub manualmente (`workflow_dispatch`).

## Testes

```bash
pytest          # 70 testes
ruff check .    # lint
mypy scripts    # tipos
```

## Importando uma planilha local

```bash
python scripts/import_agenda_xlsx.py \
  --input "/caminho/arquivo.xlsx" \
  --output data/agenda-2026-04.json \
  --monthly-page-url "https://www.gov.br/receitafederal/pt-br/assuntos/agenda-tributaria/2026/abril"
python scripts/generate_ics.py --input data/agenda-2026-04.json
python scripts/build_data_index.py
```

## Hospedagem (GitHub Pages)

Os JSONs e ICS são servidos publicamente via GitHub Pages:

- **URL base**: `https://<owner>.github.io/<repo>/data/`
- **Índice**: `https://<owner>.github.io/<repo>/data/index.json`
- **Landing**: `https://<owner>.github.io/<repo>/`
- CORS habilitado por padrão · CDN da GitHub (Fastly) · sem custo

### Pipeline completo

```
cron mensal (dia 1, 15)
    ↓
update-agenda.yml  (baixa planilha, gera JSON + ICS, atualiza index)
    ↓
abre PR automático em chore/auto-update-agenda
    ↓
merge para main (manual)
    ↓
push em data/ dispara pages.yml
    ↓
deploy no GitHub Pages (URL pública atualizada)
```

### Setup inicial (uma vez)

1. Subir o repositório no GitHub (público — Pages em repo privado exige plano pago).
2. Em **Settings → Pages**, escolher **Source: GitHub Actions**.
3. Confirmar que `pages.yml` rodou pelo menos uma vez (aba **Actions**) — vai imprimir a URL final.
4. Copiar essa URL (com sufixo `/data`) para a env `AGENDA_DATA_BASE_URL` do consumidor (no nosso caso, [contclaro-2026](../contclaro-2026)).

### Disparo manual

Em **Actions → Deploy data to GitHub Pages → Run workflow**, ou via CLI:

```bash
gh workflow run pages.yml
gh workflow run update-agenda.yml
```

## Regra de dia útil

Implementada em [scripts/holidays.py](scripts/holidays.py):

- Feriados fixos nacionais (Tiradentes, Independência, Natal, etc.)
- Móveis derivados da Páscoa (Carnaval, Sexta-feira Santa, Corpus Christi)
- Consciência Negra (20/11) — desde 2024 (Lei 14.759/2023)
- Bancários (24/12 e 31/12) — sem expediente pela ANBIMA
- **Quando o vencimento cai em dia não-útil → prorroga para o próximo dia útil** (Lei 9.430/96 art. 18)

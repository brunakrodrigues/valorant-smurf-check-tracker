# VALORANT Smurf Checker (Tracker Network API)

## O que é
App em Streamlit: você sobe uma planilha com `nick` e `tag` (Riot ID),
o app consulta o endpoint de profile do tracker.gg e tenta inferir:

- Maior elo (tier) nos **últimos 3 atos** detectados no payload
- Um "elo atual" estimado a partir do segmento competitivo mais recente
- Flag `suspeito de smurf` por heurística (ajustável na UI)

## Rodar
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Planilha
Colunas obrigatórias:
- nick
- tag

Exemplo:
| nick | tag |
|------|-----|
| nickname  | 1234 |
| nickname  | BR1 |

## Observação importante
A estrutura do payload pode variar; por isso o parser é tolerante e tenta
inferir acts/seasons via `metadata` dos `segments`.

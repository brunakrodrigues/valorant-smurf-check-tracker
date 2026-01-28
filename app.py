import pandas as pd
import streamlit as st

from tracker_client import TrackerClient, TrackerAPIError
from smurf_rules import is_suspicious_smurf, tier_to_label


# ✅ Nome exato da coluna na sua planilha
DEFAULT_RIOT_ID_COL = (
    "Insira aqui seu nick da sua conta main no Valorant (Se você colocar errado nós não vamos atrás)  "
)


def parse_riot_id(raw: str):
    """
    Aceita 'Nick#TAG' e também casos com espaços tipo 'Nick # TAG'
    Retorna (nick, tag) ou (None, None) se inválido.
    """
    if raw is None:
        return None, None
    s = str(raw).strip()
    if not s:
        return None, None
    if "#" not in s:
        return None, None

    nick, tag = s.split("#", 1)
    nick = nick.strip()
    tag = tag.strip()

    if not nick or not tag:
        return None, None

    return nick, tag


def find_riot_id_column(df: pd.DataFrame) -> str | None:
    # 1) tenta bater o nome exato (sua planilha)
    if DEFAULT_RIOT_ID_COL in df.columns:
        return DEFAULT_RIOT_ID_COL

    # 2) fallback: achar por "valorant" no nome
    lowered = {c: str(c).lower() for c in df.columns}
    candidates = [c for c, l in lowered.items() if "valorant" in l and ("nick" in l or "conta" in l)]
    if candidates:
        return candidates[0]

    # 3) fallback: procurar uma coluna que tenha muitos valores com '#'
    best_col = None
    best_score = 0
    for c in df.columns:
        ser = df[c].dropna().astype(str)
        if len(ser) == 0:
            continue
        score = (ser.str.contains("#").sum()) / len(ser)
        if score > best_score:
            best_score = score
            best_col = c

    if best_score >= 0.4:
        return best_col

    return None


st.set_page_config(page_title="VALORANT Smurf Checker (Tracker API)", layout="wide")

st.title("VALORANT — Smurf Checker (Tracker Network API)")
st.caption(
    "Upload da planilha → lê o Riot ID (Nick#Tag) → calcula maior elo nos últimos 3 atos e marca suspeita de smurf."
)

api_key = st.text_input("TRN-Api-Key (Tracker Network)", type="password")
uploaded = st.file_uploader("Suba sua planilha (.xlsx ou .csv)", type=["xlsx", "csv"])

with st.expander("Regras de suspeita (ajustável)", expanded=False):
    min_peak_tier = st.number_input("Peak mínimo (tier) p/ suspeita (ex: 18=Diamond)", value=18, step=1)
    max_current_tier = st.number_input("Atual máximo (tier) p/ suspeita (ex: 12=Gold)", value=12, step=1)
    min_gap = st.number_input("Gap mínimo (tiers) entre peak e atual", value=6, step=1)

if not api_key or not uploaded:
    st.stop()

client = TrackerClient(api_key=api_key)

# Ler arquivo
if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded)

riot_col = find_riot_id_column(df)
if not riot_col:
    st.error(
        "Não encontrei a coluna do Riot ID. "
        "A planilha precisa ter uma coluna com valores tipo Nick#TAG."
    )
    st.stop()

st.success(f"Coluna detectada para Riot ID: **{riot_col}**")

rows = []
progress = st.progress(0)
total = len(df)

for idx, row in df.iterrows():
    riot_raw = row.get(riot_col)
    nick, tag = parse_riot_id(riot_raw)

    out = {
        "riot_id_raw": None if riot_raw is None else str(riot_raw),
        "nick": nick,
        "tag": tag,
    }

    if not nick or not tag:
        out["error"] = "Riot ID inválido (esperado Nick#TAG)"
        rows.append(out)
        progress.progress(int(((idx + 1) / total) * 100))
        continue

    out["riot_id"] = f"{nick}#{tag}"

    try:
        profile = client.fetch_profile(nick, tag, force_collect=True)

        last_acts = client.infer_last_acts(profile, want=3)
        out["acts_detected"] = " | ".join([a.name for a in last_acts]) if last_acts else ""

        per_act_max, peak_last3, current_tier = client.compute_max_tier_last_acts(profile, last_acts)

        out["current_tier"] = current_tier
        out["current_rank"] = tier_to_label(current_tier)

        out["peak_last_3_acts_tier"] = peak_last3
        out["peak_last_3_acts_rank"] = tier_to_label(peak_last3)

        # colunas por ato
        for act_name, tier in per_act_max.items():
            out[f"max_{act_name}_tier"] = tier
            out[f"max_{act_name}_rank"] = tier_to_label(tier)

        suspicious, reason = is_suspicious_smurf(
            last3_peak_tier=peak_last3,
            current_tier=current_tier,
            min_peak_tier=int(min_peak_tier),
            max_current_tier=int(max_current_tier),
            min_gap=int(min_gap),
        )
        out["suspicious_smurf"] = suspicious
        out["reason"] = reason

    except TrackerAPIError as e:
        out["error"] = str(e)
    except Exception as e:
        out["error"] = f"Erro inesperado: {e}"

    rows.append(out)
    progress.progress(int(((idx + 1) / total) * 100))

result_df = pd.DataFrame(rows)

st.subheader("Resultado")
st.dataframe(result_df, use_container_width=True)

st.download_button(
    "Baixar resultado (.csv)",
    data=result_df.to_csv(index=False).encode("utf-8"),
    file_name="smurf_check_result.csv",
    mime="text/csv",
)

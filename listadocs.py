"""
listadocs.py - painel dos documentos: quem tem e quem não tem registro em blockchain

A situação do registro vem do próprio MongoDB (campo blockchain_info) e é instantânea.
Opcionalmente, confere cada registro na Celo Sepolia (recalcula o hash e consulta o contrato).
"""
import csv
import io
import json

import streamlit as st

import celo_common as cc

cc.configurar_pagina("Documentos - Celo", "📚")

ROTULO_INTEGRIDADE = {
    "integro": "✅ Íntegro",
    "integro_aviso": "✅ Íntegro (aviso)",
    "modificado": "🚨 Modificado",
    "inexistente_na_cadeia": "🚨 Não existe na cadeia",
    "invalidado": "🔴 Invalidado",
    "divergente": "🚨 Record ID divergente",
    "legado_ok": "📄 Legado (confere)",
    "legado_modificado": "🚨 Legado modificado",
    "sem_rpc": "📡 Sem conexão",
    "sem_registro": "—",
}

st.title("📚 Documentos e Situação na Blockchain")
st.markdown("Lista os documentos da coleção e mostra quais já têm registro em blockchain e quais ainda não têm.")
st.markdown("---")

coll = cc.conexao_mongo("lst")
if coll is None:
    st.stop()

# ---------- filtros ----------
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    filtro = st.radio("Mostrar", ["Todos", "Com registro", "Sem registro"], horizontal=True, key="lst_filtro")
with c2:
    busca = st.text_input("Buscar por ID do atendimento ou tipo", key="lst_busca", placeholder="ex.: ATND-2026 ou Vacinação")
with c3:
    limite = st.number_input("Máximo", min_value=10, max_value=5000, value=500, step=50, key="lst_limite")

consulta = {}
if filtro == "Com registro":
    consulta["blockchain_info.document_hash"] = {"$exists": True}
elif filtro == "Sem registro":
    consulta["blockchain_info.document_hash"] = {"$exists": False}
if busca.strip():
    termo = {"$regex": busca.strip(), "$options": "i"}
    consulta["$or"] = [{"idAtendimento": termo}, {"tipoAtendimento": termo}]

try:
    docs = list(coll.find(consulta).sort("_id", -1).limit(int(limite)))
    total_banco = coll.count_documents({})
    com_registro = coll.count_documents({"blockchain_info.document_hash": {"$exists": True}})
except Exception as e:
    st.error(f"❌ Erro ao consultar: {e}")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total na coleção", total_banco)
m2.metric("✅ Com registro", com_registro)
m3.metric("⏳ Sem registro", total_banco - com_registro)
m4.metric("Exibidos", len(docs))

# ---------- conferência on-chain (opcional) ----------
conferir = st.toggle("🔍 Conferir integridade na blockchain (recalcula o hash e consulta o contrato de cada registro)",
                     key="lst_conferir",
                     help="Mais lento: uma consulta à Celo Sepolia por documento registrado.")
integridade = {}
if conferir:
    registrados = [d for d in docs if cc.situacao_registro(d) != "sem"]
    contract = None
    try:
        contract = cc.get_contract(cc.get_web3())
    except Exception as e:
        st.warning(f"Sem conexão com a Celo Sepolia: {e}")
    barra = st.progress(0.0, text="Conferindo...")
    for i, d in enumerate(registrados, start=1):
        try:
            integridade[d["_id"]] = cc.verificar_integridade(d, contract, tentativas=1)["status"]
        except Exception:
            integridade[d["_id"]] = "sem_rpc"
        barra.progress(i / max(len(registrados), 1), text=f"Conferindo {i}/{len(registrados)}...")
    barra.empty()
    problemas = sum(1 for s in integridade.values() if s not in ("integro", "integro_aviso", "legado_ok"))
    if registrados:
        (st.error if problemas else st.success)(
            f"{len(registrados) - problemas} de {len(registrados)} registro(s) conferido(s) sem problema"
            + (f" · {problemas} com alerta" if problemas else "") + ".")

# ---------- tabela ----------
linhas = []
for d in docs:
    info = d.get("blockchain_info") or {}
    sit = cc.situacao_registro(d)
    linha = {
        "_id": str(d["_id"]),
        "ID atendimento": d.get("idAtendimento", ""),
        "Data/hora": str(d.get("dataHoraAtendimento", ""))[:16].replace("T", " "),
        "Tipo": d.get("tipoAtendimento", ""),
        "CNS": cc.mascarar_cns(d.get("cnsPaciente")),
        "Blockchain": cc.SITUACAO_REGISTRO[sit],
        "Rede": info.get("network", "") if sit != "sem" else "",
        "Bloco": str(info.get("transaction", {}).get("block_number", "")) if sit != "sem" else "",
        "Registrado em": str(info.get("registered_at", ""))[:16].replace("T", " ") if sit != "sem" else "",
        "Explorer": info.get("explorer_url") or info.get("etherscan_url") or None,
    }
    if conferir:
        linha["Integridade"] = ROTULO_INTEGRIDADE.get(integridade.get(d["_id"], "sem_registro"), "—")
    linhas.append(linha)

if not linhas:
    st.info("Nenhum documento encontrado com esses filtros.")
    st.stop()

st.dataframe(
    linhas, hide_index=True, width="stretch",
    column_config={"Explorer": st.column_config.LinkColumn("Explorer", display_text="abrir")},
)

buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=list(linhas[0].keys()), delimiter=";")
w.writeheader()
w.writerows(linhas)
st.download_button("⬇️ Baixar lista (CSV)", buf.getvalue().encode("utf-8-sig"), file_name="documentos_blockchain.csv",
                   mime="text/csv")

# ---------- detalhe ----------
st.markdown("---")
st.subheader("📄 Ver um documento")
opcoes = {f'{l["ID atendimento"]} · {l["Blockchain"]} · {l["_id"]}': i for i, l in enumerate(linhas)}
escolha = st.selectbox("Documento", list(opcoes.keys()), key="lst_escolha")
doc = docs[opcoes[escolha]]
st.code(str(doc["_id"]), language=None)
st.caption("Copie o _id acima para usar em “Registrar documento” ou “Verificar integridade”.")
with st.expander("JSON completo", expanded=False):
    mostrar = json.loads(json.dumps(doc, default=str, ensure_ascii=False))
    (mostrar.get("blockchain_info") or {}).pop("salt", None)   # o salt não é exibido
    st.json(mostrar)

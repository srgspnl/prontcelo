import json
from datetime import datetime

import streamlit as st
from bson.objectid import ObjectId
from pymongo import MongoClient

import celo_common as cc

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(page_title="Verificador de Integridade - Celo", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .integrity-box-valid { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white;
        padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0; }
    .integrity-box-invalid { background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%); color: white;
        padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0; }
    .integrity-box-none { background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%); color: white;
        padding: 20px; border-radius: 10px; text-align: center; margin: 10px 0; }
    .hash-display { font-family: monospace; font-size: 0.9em; background-color: #f5f5f5; color: #222;
        padding: 10px; border-radius: 5px; word-break: break-all; }
</style>
""", unsafe_allow_html=True)

# status -> (classe CSS, título, subtítulo)
APARENCIA = {
    "integro":               ("valid",   "✅ DOCUMENTO ÍNTEGRO", "O conteúdo atual corresponde ao hash registrado na blockchain"),
    "integro_aviso":         ("valid",   "✅ DOCUMENTO ÍNTEGRO (com aviso)", "O conteúdo confere, mas o hash guardado no Mongo foi alterado"),
    "modificado":            ("invalid", "⚠️ DOCUMENTO MODIFICADO", "O conteúdo atual NÃO está registrado na blockchain"),
    "inexistente_na_cadeia": ("invalid", "🚨 REGISTRO ON-CHAIN INEXISTENTE", "O hash do Mongo confere, mas não existe no contrato"),
    "invalidado":            ("invalid", "🔴 HASH INVALIDADO", "O registro foi invalidado depois no contrato"),
    "divergente":            ("invalid", "🚨 RECORD ID DIVERGENTE", "O hash existe, mas pertence a outro documento"),
    "legado_ok":             ("none",    "📄 REGISTRO LEGADO", "Sem confirmação on-chain neste app (hash do Mongo confere)"),
    "legado_modificado":     ("invalid", "⚠️ REGISTRO LEGADO MODIFICADO", "O conteúdo não confere com o hash guardado"),
    "sem_rpc":               ("none",    "📡 SEM CONEXÃO COM A CELO", "Não foi possível confirmar on-chain"),
    "sem_registro":          ("none",    "📄 SEM REGISTRO BLOCKCHAIN", "Este documento não possui informações de blockchain"),
}

# ==================== INTERFACE ====================
st.title("🔍 Verificador de Integridade de Documentos")
st.markdown(f"### Sistema de Verificação de Hash - MongoDB × {cc.NETWORK_NAME}")
st.markdown("---")

if "mongodb_connected" not in st.session_state:
    st.session_state.mongodb_connected = False
    st.session_state.documento = None

# ==================== CONEXÃO MONGODB ====================
if not st.session_state.mongodb_connected:
    st.subheader("📊 Conectar ao MongoDB")

    with st.form("mongodb_credentials"):
        col1, col2 = st.columns(2)
        with col1:
            usuario = st.text_input("Usuário", value="admin")
            database = st.text_input("Database", value="context")
        with col2:
            senha_mongodb = st.text_input(
                "Senha MongoDB", type="password",
                help="Digite 12 caracteres (apenas os 8 primeiros serão usados). "
                     "Dispensável se MONGO_SENHA estiver no senhas.txt.")
            collection = st.text_input("Coleção", value="SaudeTeste")

        host = st.text_input("Host/Cluster", value="cluster0.rfdha.gcp.mongodb.net")
        object_id_input = st.text_input("ObjectId (_id) do Documento",
                                        help="Digite o _id do documento que será verificado")
        submit_mongo = st.form_submit_button("🔌 Conectar e Buscar Documento", use_container_width=True)

    if submit_mongo:
        if not senha_mongodb and not cc.MONGO_PRONTA:
            st.error("⚠️ Por favor, informe a senha do MongoDB.")
        elif not cc.MONGO_PRONTA and len(senha_mongodb) < 12:
            st.error("⚠️ A senha deve ter exatamente 12 caracteres.")
        elif not object_id_input:
            st.error("⚠️ Por favor, informe o ObjectId do documento.")
        else:
            try:
                with st.spinner("🔄 Conectando ao MongoDB..."):
                    mongo_client = MongoClient(
                        cc.build_mongo_uri(usuario, senha_mongodb, host, database),
                        serverSelectionTimeoutMS=5000)
                    coll = mongo_client[database][collection]
                    mongo_client.server_info()

                    object_id = ObjectId(object_id_input.strip())
                    documento = coll.find_one({"_id": object_id})

                    if not documento:
                        st.error(f"❌ Documento com _id '{object_id_input}' não encontrado!")
                        mongo_client.close()
                    else:
                        st.session_state.mongodb_connected = True
                        st.session_state.documento = documento
                        st.session_state.object_id = object_id
                        st.session_state.mongo_client = mongo_client
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao conectar: {e}")

# ==================== VERIFICAÇÃO ====================
if st.session_state.mongodb_connected:
    st.success("✅ Conectado ao MongoDB com sucesso!")

    documento = st.session_state.documento
    object_id = st.session_state.object_id
    info = documento.get("blockchain_info") or {}

    st.subheader("📄 Documento Encontrado")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ObjectId", str(object_id)[:12] + "...")
    with col2:
        st.metric("ID Atendimento", documento.get("idAtendimento", "N/A"))
    with col3:
        cns = str(documento.get("cnsPaciente") or "")
        st.metric("CNS Paciente", ("•" * max(len(cns) - 4, 0) + cns[-4:]) if cns else "N/A")

    st.markdown("---")
    st.subheader("🔍 Verificação de Integridade")

    # Consulta a blockchain (somente leitura; não precisa de carteira nem chave)
    contract, aviso_rpc = None, None
    if info:
        try:
            with st.spinner("Consultando a Celo Sepolia..."):
                contract = cc.get_contract(cc.get_web3())
        except Exception as e:
            aviso_rpc = str(e)

    with st.spinner("Verificando integridade..."):
        r = cc.verificar_integridade(documento, contract)

    classe, titulo, sub = APARENCIA.get(r["status"], ("none", r["status"], ""))
    st.markdown(f"""
    <div class="integrity-box-{classe}">
        <h2 style="margin: 0;">{titulo}</h2>
        <p style="margin: 10px 0 0 0; font-size: 1.1em;">{sub}</p>
    </div>
    """, unsafe_allow_html=True)
    st.write(r["mensagem"])
    if aviso_rpc:
        st.warning(f"Detalhe da conexão: {aviso_rpc}")

    if r["hash_armazenado"]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📊 Hash Armazenado (Mongo)")
            st.markdown(f'<div class="hash-display">{r["hash_armazenado"]}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown("#### 🔐 Hash Calculado (conteúdo atual)")
            st.markdown(f'<div class="hash-display">{r["hash_calculado"]}</div>', unsafe_allow_html=True)

    oc = r["onchain"]
    if oc:
        st.markdown("---")
        st.subheader("⛓️ O que a blockchain diz sobre o hash calculado")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Existe no contrato", "Sim" if oc["exists"] else "Não")
        with c2:
            st.metric("Status", ("🟢 Válido" if oc["is_valid"] else "🔴 Invalidado") if oc["exists"] else "N/A")
        with c3:
            st.metric("Registrado em (UTC)", oc["datetime"][:19].replace("T", " ") if oc["datetime"] else "N/A")
        with c4:
            st.metric("Provedor", (oc["provider"][:8] + "...") if oc["exists"] else "N/A")
        if oc["exists"]:
            st.caption(f"Tipo: {oc['record_type']} · Record ID: {oc['record_id']}")
    if r["onchain_armazenado"] is not None:
        oa = r["onchain_armazenado"]
        st.info("O hash ORIGINAL (guardado no Mongo) "
                + ("existe na blockchain: o registro é genuíno e o documento foi alterado depois."
                   if oa["exists"] else "também não existe na blockchain."))

    if info:
        st.markdown("---")
        st.subheader("📋 Informações do Registro Blockchain")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            reg = info.get("registered_at", "N/A")
            try:
                dt = datetime.fromisoformat(reg)
                st.metric("Data de Registro", dt.strftime("%d/%m/%Y"))
                st.caption(dt.strftime("%H:%M:%S"))
            except Exception:
                st.metric("Data de Registro", str(reg)[:10])
        with c2:
            tx = info.get("transaction", {}).get("transaction_hash", "N/A")
            st.metric("TX Hash", tx[:8] + "..." if tx != "N/A" else "N/A")
        with c3:
            bn = info.get("transaction", {}).get("block_number", "N/A")
            st.metric("Bloco", f"#{bn}" if bn != "N/A" else "N/A")
        with c4:
            st.metric("Rede", info.get("network", "N/A"))

        with st.expander("🔍 Ver Detalhes Completos do Blockchain"):
            st.json({k: v for k, v in info.items() if k != "salt"})  # o salt não é exibido

        url = info.get("explorer_url") or info.get("etherscan_url")
        if url:
            st.link_button("🔗 Ver Transação no Explorer", url, use_container_width=True)

    st.markdown("---")
    with st.expander("📄 Ver Documento Completo (JSON)", expanded=False):
        st.json(json.loads(json.dumps(documento, default=str, ensure_ascii=False)))

    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Verificar Outro Documento", use_container_width=True):
            st.session_state.mongodb_connected = False
            st.session_state.mongo_client.close()
            st.rerun()

st.markdown("---")
st.caption("🔒 Verificação somente leitura: consulta o MongoDB e o contrato na Celo Sepolia (nenhuma transação é enviada).")
st.caption("💡 A prova de integridade é o hash recalculado existir e ser válido na blockchain - não o hash guardado no Mongo.")

import json
from datetime import datetime, timezone

import streamlit as st
from bson.objectid import ObjectId
from pymongo import MongoClient

import celo_common as cc

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(page_title="Registro Blockchain - Celo", page_icon="🔗", layout="wide")


def mascarar_cns(cns):
    cns = str(cns or "")
    return "•" * max(len(cns) - 4, 0) + cns[-4:] if cns else "N/A"


def resetar():
    st.session_state.mongodb_connected = False
    client = st.session_state.get("mongo_client")
    if client:
        client.close()
    st.session_state.pop("salt_doc", None)
    st.rerun()


# ==================== INTERFACE ====================
st.title("🔗 Registro de Documentos no Blockchain")
st.markdown(f"### Sistema de Registro - {cc.NETWORK_NAME}")
st.caption(f"Contrato: `{cc.CONTRACT_ADDRESS}` · Chain ID {cc.CHAIN_ID}")
st.markdown("---")

if "mongodb_connected" not in st.session_state:
    st.session_state.mongodb_connected = False
    st.session_state.documento = None

# ==================== ETAPA 1: CREDENCIAIS MONGODB ====================
if not st.session_state.mongodb_connected:
    st.subheader("📊 Etapa 1: Conectar ao MongoDB")

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
        object_id_input = st.text_input(
            "ObjectId (_id) do Documento",
            help="Digite o _id do documento que será registrado no blockchain")
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
                        st.session_state.object_id = object_id
                        st.session_state.mongo_client = mongo_client
                        st.session_state.collection = coll
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao conectar: {e}")

# ==================== ETAPA 2: VISUALIZAR E REGISTRAR ====================
if st.session_state.mongodb_connected:
    coll = st.session_state.collection
    object_id = st.session_state.object_id
    documento = coll.find_one({"_id": object_id})  # sempre o estado ATUAL do banco

    if documento is None:
        st.error("❌ O documento não existe mais no MongoDB.")
        if st.button("🔄 Voltar"):
            resetar()
        st.stop()

    st.success("✅ Conectado ao MongoDB com sucesso!")
    st.subheader("📄 Documento Encontrado")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ObjectId", str(object_id)[:12] + "...")
    with col2:
        st.metric("ID Atendimento", documento.get("idAtendimento", "N/A"))
    with col3:
        st.metric("CNS Paciente", mascarar_cns(documento.get("cnsPaciente")))

    with st.expander("🔍 Ver Documento Completo (JSON)", expanded=False):
        st.json(json.loads(json.dumps(documento, default=str, ensure_ascii=False)))

    st.markdown("---")

    # ---------- já registrado: não registra de novo ----------
    info_existente = documento.get("blockchain_info")
    if info_existente:
        st.warning("⚠️ Este documento já possui registro em blockchain. Um novo registro não é permitido.")
        url = info_existente.get("explorer_url") or info_existente.get("etherscan_url")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Rede", info_existente.get("network", "N/A"))
        with c2:
            st.metric("Bloco", f"#{info_existente.get('transaction', {}).get('block_number', 'N/A')}")
        if url:
            st.link_button("🔗 Ver transação no explorer", url)
        st.info("Para conferir a integridade use o verificador (verificahash.py).")
    else:
        # ---------- hash do documento (salt fixo durante a sessão do documento) ----------
        if st.session_state.get("salt_doc") != str(object_id):
            st.session_state.salt = cc.new_salt()
            st.session_state.salt_doc = str(object_id)
        salt = st.session_state.salt

        st.subheader("🔐 Hash do Documento")
        hash_hex, canonico = cc.gerar_hash_documento(documento, salt)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.code(hash_hex, language=None)
        with col2:
            st.info(f"📊 SHA-256 sobre {len(canonico)} caracteres (JSON canônico + salt)")

        with st.expander("🔍 Ver JSON canônico (base do hash)"):
            st.text_area("Documento sem _id, blockchain_info e status do registro",
                         canonico[:2000] + ("..." if len(canonico) > 2000 else ""), height=200)

        st.markdown("---")

        # ---------- registro ----------
        st.subheader("🔗 Etapa 2: Registrar no Blockchain")

        with st.form("blockchain_form"):
            st.markdown("**Credenciais da Carteira (Celo Sepolia - somente conta de teste)**")
            private_key = st.text_input(
                "Chave Privada (sem 0x)", type="password",
                help="Conta autorizada como provedor no contrato. "
                     "Dispensável se CELO_PRIVATE_KEY estiver no senhas.txt.")
            record_type = st.text_input(
                "Tipo de Registro",
                value=documento.get("tipoAtendimento", "atendimento_saude"),
                help="Nunca informe dados pessoais: este texto fica público na blockchain.")
            submit_blockchain = st.form_submit_button("🚀 Registrar no Blockchain Celo Sepolia",
                                                      use_container_width=True)

        if submit_blockchain:
            chave = private_key or cc.PRIVATE_KEY_ENV
            if not chave:
                st.error("⚠️ Por favor, informe a chave privada.")
                st.stop()
            try:
                with st.spinner("🔄 Conectando à Celo Sepolia..."):
                    w3 = cc.get_web3()
                    contract = cc.get_contract(w3)
                st.success(f"✅ Conectado à {cc.NETWORK_NAME} (chain {w3.eth.chain_id})")

                account = w3.eth.account.from_key(chave.strip().removeprefix("0x"))
                saldo = w3.from_wei(w3.eth.get_balance(account.address), "ether")
                st.info(f"👤 Conta: {account.address} · 💰 {saldo:.4f} CELO")
                if saldo == 0:
                    st.error("❌ Saldo zero. Obtenha CELO de teste no faucet.")
                    st.link_button("Faucet Celo Sepolia", cc.FAUCET_URL)
                    st.stop()

                if not contract.functions.isProviderAuthorized(account.address).call():
                    st.error("❌ Sua conta não está autorizada como provedor!")
                    st.info("💡 Apenas contas autorizadas (authorizeProvider) podem registrar hashes.")
                    st.stop()
                st.success("✅ Conta autorizada como provedor!")

                # Recalcula com o documento mais recente imediatamente antes de enviar
                atual = coll.find_one({"_id": object_id})
                if atual is None or atual.get("blockchain_info"):
                    st.error("❌ O documento mudou (foi removido ou já registrado). Recarregue.")
                    st.stop()
                hash_hex, _ = cc.gerar_hash_documento(atual, salt)
                record_id = str(object_id)

                st.markdown("---")
                st.subheader("📝 Registrando Hash no Blockchain...")
                with st.spinner("⏳ Enviando transação e aguardando confirmação..."):
                    res = cc.registrar_on_chain(w3, contract, chave, hash_hex, record_type, record_id)
                receipt, tx_hash_hex = res["receipt"], res["tx_hash"]

                st.info(f"🔗 Transação: {tx_hash_hex}")
                st.link_button("🔍 Ver no Blockscout", cc.explorer_tx_url(tx_hash_hex))
                st.success("✅ HASH REGISTRADO COM SUCESSO!")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Bloco", f"#{receipt.blockNumber}")
                with c2:
                    st.metric("Gas Usado", f"{receipt.gasUsed:,}")
                with c3:
                    st.metric("Evento HashRegistered", "✅ Confirmado" if res["event_ok"] else "⚠️ Não localizado")

                # ---------- verificação on-chain (com repetição: o RPC público pode estar atrasado) ----------
                st.markdown("---")
                st.subheader("🔍 Verificação no Blockchain")
                with st.spinner("Aguardando propagação do bloco e verificando..."):
                    ver = cc.verificar_on_chain(contract, hash_hex, tentativas=15, intervalo=2.0)

                if ver["exists"]:
                    st.success("✅ Hash encontrado e verificado no blockchain!")
                    d_local = datetime.fromtimestamp(ver["timestamp"], tz=timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Status:**", "🟢 VÁLIDO" if ver["is_valid"] else "🔴 INVÁLIDO")
                        st.write("**Data de Registro:**", d_local)
                        st.write("**Provedor:**", ver["provider"])
                    with c2:
                        st.write("**Tipo:**", ver["record_type"])
                        st.write("**Record ID:**", ver["record_id"])
                        st.write("**Integridade:**",
                                 "✅ OK" if ver["record_type"] == record_type and ver["record_id"] == record_id
                                 else "⚠️ Divergência")
                else:
                    st.warning("⚠️ A transação foi confirmada, mas o nó de leitura ainda não devolveu o registro. "
                               "Isso é atraso de propagação; use o verificador em instantes.")

                # ---------- atualiza o MongoDB ----------
                st.markdown("---")
                st.subheader("💾 Atualizando MongoDB")
                blockchain_info = {
                    "document_hash": hash_hex,
                    "hash_scheme": cc.HASH_SCHEME,
                    "salt": salt,
                    "transaction": {
                        "transaction_hash": tx_hash_hex,
                        "block_number": receipt.blockNumber,
                        "gas_used": receipt.gasUsed,
                        "transaction_status": "success",
                        "event_confirmed": res["event_ok"],
                    },
                    "verification": ver,
                    "contract_address": cc.CONTRACT_ADDRESS,
                    "network": cc.NETWORK_NAME,
                    "chain_id": cc.CHAIN_ID,
                    "registered_by": res["from"],
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "explorer_url": cc.explorer_tx_url(tx_hash_hex),
                }
                try:
                    r = coll.update_one(
                        {"_id": object_id},
                        {"$set": {"blockchain_info": blockchain_info,
                                  "dadosClinicosGerais.statusRegistroBlockchain": cc.STATUS_REGISTRADO}})
                    if r.matched_count:
                        st.success("✅ Documento atualizado no MongoDB com informações da blockchain!")
                        st.balloons()
                    else:
                        raise RuntimeError("documento não encontrado para atualização")
                except Exception as e:
                    st.error(f"❌ O hash foi registrado na blockchain, mas a atualização do MongoDB falhou: {e}")
                    st.warning("Guarde os dados abaixo (incluindo o salt) para gravar manualmente em blockchain_info.")
                    st.json(blockchain_info)

            except ValueError as e:
                st.warning(f"⚠️ {e}")
            except Exception as e:
                st.error(f"❌ Erro: {e}")

    st.markdown("---")
    if st.button("🔄 Registrar Outro Documento"):
        resetar()

"""
celo_common.py - módulo compartilhado (Celo Sepolia + MongoDB)

Usado por app.py (menu de entrada) e pelas telas inserirdoc, listadocs, insertreg e verificahash.

Nenhuma senha é armazenada: não há senhas.txt, secrets.toml nem variáveis de ambiente.
- Senha do MongoDB: pedida na tela a cada conexão, com OFUSCAMENTO. O usuário digita
  12 caracteres e o código usa apenas os 8 primeiros (os 4 últimos são preenchimento).
- Chave privada da carteira: pedida na tela a cada registro e usada só naquela transação.
"""
import re
import json
import time
import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import quote_plus

from bson.json_util import dumps as _bson_dumps, RELAXED_JSON_OPTIONS
from web3 import Web3


# ==================== OFUSCAMENTO DA SENHA DO MONGODB ====================
SENHA_DIGITADA_TAM = 12      # quantos caracteres o usuário digita
SENHA_REAL_TAM = 8           # quantos o código usa (os primeiros)
AJUDA_SENHA_MONGO = (f"Digite {SENHA_DIGITADA_TAM} caracteres: os {SENHA_REAL_TAM} primeiros são a senha real "
                     f"e os {SENHA_DIGITADA_TAM - SENHA_REAL_TAM} últimos são preenchimento. A senha não é armazenada.")
AJUDA_CHAVE_PRIVADA = ("Chave privada da carteira autorizada (64 caracteres hexadecimais, com ou sem 0x). "
                       "É usada só nesta transação e não é armazenada.")


def validar_senha_mongo(senha):
    """Devolve uma mensagem de erro, ou None se a senha digitada está no formato esperado."""
    if not senha:
        return "Informe a senha do MongoDB."
    if len(senha) != SENHA_DIGITADA_TAM:
        return (f"A senha deve ter exatamente {SENHA_DIGITADA_TAM} caracteres "
                f"(foram digitados {len(senha)}).")
    return None


def validar_chave_privada(chave):
    """Devolve (chave_normalizada_sem_0x, mensagem_de_erro)."""
    chave = (chave or "").strip()
    chave = chave[2:] if chave.lower().startswith("0x") else chave
    if not chave:
        return None, "Informe a chave privada da carteira."
    if not re.fullmatch(r"[0-9a-fA-F]{64}", chave):
        return None, "A chave privada deve ter 64 caracteres hexadecimais (0-9, a-f)."
    return chave, None


def configurar_pagina(titulo, icone):
    """set_page_config tolerante: dentro do menu (app.py) a página já foi configurada."""
    import streamlit as st
    try:
        st.set_page_config(page_title=titulo, page_icon=icone, layout="wide")
    except Exception:
        pass


# ==================== REDE / CONTRATO ====================
NETWORK_NAME = "Celo Sepolia Testnet"
CHAIN_ID = 11142220
RPC_URL = "https://forno.celo-sepolia.celo-testnet.org"
EXPLORER_URL = "https://celo-sepolia.blockscout.com"
FAUCET_URL = "https://faucet.celo.org/celo-sepolia"
CONTRACT_ADDRESS = Web3.to_checksum_address("0xfe35a002800711b3f969fe286d0370335bc73852")

HASH_SCHEME = "canonical-json-sha256-salt-v2"
STATUS_PENDENTE = "Pendente de Validação"
STATUS_REGISTRADO = "Atendimento concluído e registro on-chain enviado"

CONTRACT_ABI = json.loads(r"""
[
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "hash",
        "type": "bytes32"
      },
      {
        "indexed": true,
        "internalType": "address",
        "name": "provider",
        "type": "address"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "recordType",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "recordId",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "uint256",
        "name": "timestamp",
        "type": "uint256"
      }
    ],
    "name": "HashRegistered",
    "type": "event"
  },
  {
    "inputs": [],
    "name": "admin",
    "outputs": [
      {
        "internalType": "address",
        "name": "",
        "type": "address"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "address",
        "name": "_provider",
        "type": "address"
      }
    ],
    "name": "isProviderAuthorized",
    "outputs": [
      {
        "internalType": "bool",
        "name": "",
        "type": "bool"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_hash",
        "type": "bytes32"
      },
      {
        "internalType": "string",
        "name": "_recordType",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_recordId",
        "type": "string"
      }
    ],
    "name": "registerHash",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_hash",
        "type": "bytes32"
      }
    ],
    "name": "verifyHash",
    "outputs": [
      {
        "internalType": "bool",
        "name": "exists",
        "type": "bool"
      },
      {
        "internalType": "bool",
        "name": "isValid",
        "type": "bool"
      },
      {
        "internalType": "uint256",
        "name": "timestamp",
        "type": "uint256"
      },
      {
        "internalType": "address",
        "name": "provider",
        "type": "address"
      },
      {
        "internalType": "string",
        "name": "recordType",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "recordId",
        "type": "string"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  }
]
""")


def explorer_tx_url(tx_hash):
    return f"{EXPLORER_URL}/tx/{tx_hash}"


def get_web3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise ConnectionError(f"Não foi possível conectar ao RPC da Celo Sepolia ({RPC_URL}).")
    if w3.eth.chain_id != CHAIN_ID:
        raise ValueError(
            f"RPC está na rede errada (chain_id {w3.eth.chain_id}; esperado {CHAIN_ID} - {NETWORK_NAME})."
        )
    return w3


def get_contract(w3):
    return w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)


# ==================== MONGODB ====================
def build_mongo_uri(usuario, senha, host, database):
    """Monta a URI do MongoDB Atlas. OFUSCAMENTO: da senha digitada (12 caracteres),
    só os 8 primeiros são usados. Valide antes com validar_senha_mongo()."""
    senha_real = senha[:SENHA_REAL_TAM]
    return (f"mongodb+srv://{quote_plus(usuario)}:{quote_plus(senha_real)}"
            f"@{host}/{database}?retryWrites=true&w=majority")


# ==================== HASH DO DOCUMENTO ====================
def new_salt():
    return secrets.token_hex(16)


def normalizar_hash(h):
    h = (h or "").strip().lower()
    return h[2:] if h.startswith("0x") else h


def to_bytes32(hash_hex):
    h = normalizar_hash(hash_hex)
    if len(h) != 64:
        raise ValueError("O hash deve ter 64 caracteres hexadecimais.")
    return bytes.fromhex(h)


def documento_canonico(documento):
    """JSON canônico do documento (chaves ordenadas, sem espaços).
    Fica de fora o que muda DEPOIS do registro: _id, blockchain_info e o status do registro."""
    d = json.loads(_bson_dumps(documento, json_options=RELAXED_JSON_OPTIONS))
    d.pop("_id", None)
    d.pop("blockchain_info", None)
    dcg = d.get("dadosClinicosGerais")
    if isinstance(dcg, dict):
        dcg.pop("statusRegistroBlockchain", None)
        if not dcg:
            d.pop("dadosClinicosGerais")
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def gerar_hash_documento(documento, salt):
    """SHA-256( salt + ':' + JSON canônico ). O salt impede ataque de dicionário
    sobre o hash público e fica guardado em blockchain_info.salt."""
    canonico = documento_canonico(documento)
    hash_hex = hashlib.sha256(f"{salt}:{canonico}".encode("utf-8")).hexdigest()
    return hash_hex, canonico


def _valores(obj, acc):
    if isinstance(obj, dict):
        for k in sorted(obj.keys()):
            _valores(obj[k], acc)
    elif isinstance(obj, list):
        for item in obj:
            _valores(item, acc)
    else:
        acc.append(str(obj))
    return acc


def gerar_hash_legado(documento):
    """Esquema antigo (registros da Ethereum Sepolia): concatenação só dos valores."""
    d = dict(documento)
    d.pop("_id", None)
    d.pop("blockchain_info", None)
    texto = "".join(_valores(d, []))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest(), texto


# ==================== BLOCKCHAIN ====================
def verificar_on_chain(contract, hash_hex, tentativas=1, intervalo=2.0):
    """Consulta verifyHash. O RPC público balanceia entre nós e um nó atrasado pode ainda
    não ter o bloco recém-confirmado; por isso há repetição quando o hash não aparece."""
    h = to_bytes32(hash_hex)
    for i in range(max(1, tentativas)):
        exists, is_valid, ts, provider, rtype, rid = contract.functions.verifyHash(h).call()
        if exists:
            break
        if i < tentativas - 1:
            time.sleep(intervalo)
    return {
        "exists": exists,
        "is_valid": is_valid,
        "timestamp": ts,
        "datetime": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if exists else None,
        "provider": provider,
        "record_type": rtype,
        "record_id": rid,
    }


def registrar_on_chain(w3, contract, private_key, hash_hex, record_type, record_id):
    pk = private_key.strip()
    pk = pk[2:] if pk.startswith("0x") else pk
    account = w3.eth.account.from_key(pk)
    h = to_bytes32(hash_hex)

    if contract.functions.verifyHash(h).call()[0]:
        raise ValueError("Este hash já está registrado no contrato.")

    base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
    tip = w3.to_wei(2, "gwei")
    tx = contract.functions.registerHash(h, record_type, record_id).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "maxFeePerGas": base_fee * 2 + tip,
        "maxPriorityFeePerGas": tip,
    })  # o gas é estimado aqui; se a transação fosse reverter, o erro aparece antes de enviar
    tx["gas"] = int(tx["gas"] * 1.3)

    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction  # web3 v7 / v6
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        raise RuntimeError("A transação foi revertida pela rede.")

    eventos = contract.events.HashRegistered().process_receipt(receipt)
    return {
        "tx_hash": w3.to_hex(tx_hash),
        "receipt": receipt,
        "from": account.address,
        "event_ok": any(e["args"]["hash"] == h for e in eventos),
    }


# ==================== VERIFICAÇÃO DE INTEGRIDADE ====================
def verificar_integridade(documento, contract=None, tentativas=3):
    """Compara o documento ATUAL do Mongo com o que está na blockchain.
    O hash guardado no próprio Mongo NÃO é prova: quem altera o documento pode alterar
    esse campo também. A prova é o hash recalculado existir (e ser válido) no contrato."""
    info = documento.get("blockchain_info") or {}
    r = {"status": None, "mensagem": "", "hash_armazenado": None, "hash_calculado": None,
         "onchain": None, "onchain_armazenado": None}

    if not info:
        r.update(status="sem_registro", mensagem="Documento não possui informações de blockchain.")
        return r
    armazenado = normalizar_hash(info.get("document_hash"))
    if not armazenado:
        r.update(status="sem_registro", mensagem="Hash não encontrado em blockchain_info.")
        return r

    r["hash_armazenado"] = armazenado
    novo_esquema = info.get("hash_scheme") == HASH_SCHEME
    if novo_esquema:
        calculado, _ = gerar_hash_documento(documento, info.get("salt", ""))
    else:
        calculado, _ = gerar_hash_legado(documento)
    r["hash_calculado"] = calculado
    bate = calculado == armazenado

    desta_rede = (novo_esquema
                  and info.get("chain_id") == CHAIN_ID
                  and str(info.get("contract_address", "")).lower() == CONTRACT_ADDRESS.lower())
    if not desta_rede:
        r["status"] = "legado_ok" if bate else "legado_modificado"
        r["mensagem"] = (
            "Registro de outra rede/contrato (ex.: Ethereum Sepolia). Só foi possível comparar com o hash "
            "guardado no Mongo - sem confirmação on-chain neste app."
        )
        return r

    if contract is None:
        r["status"] = "sem_rpc"
        r["mensagem"] = "Não foi possível consultar a Celo Sepolia; resultado sem confirmação on-chain."
        return r

    oc = verificar_on_chain(contract, calculado, tentativas=tentativas, intervalo=1.5)
    r["onchain"] = oc
    id_confere = oc["record_id"] == str(documento.get("_id"))

    if oc["exists"] and not oc["is_valid"]:
        r.update(status="invalidado", mensagem="Hash registrado, mas INVALIDADO depois no contrato.")
    elif oc["exists"] and not id_confere:
        r.update(status="divergente",
                 mensagem="O hash existe na cadeia, mas está associado a outro Record ID.")
    elif oc["exists"] and bate:
        r.update(status="integro", mensagem="Documento íntegro: o conteúdo atual corresponde ao hash registrado na blockchain.")
    elif oc["exists"]:
        r.update(status="integro_aviso",
                 mensagem="Conteúdo íntegro (hash recalculado existe na cadeia), mas o hash guardado no Mongo foi alterado.")
    elif bate:
        r.update(status="inexistente_na_cadeia",
                 mensagem="O hash guardado no Mongo confere com o documento, mas NÃO existe no contrato: o registro on-chain é inexistente ou falso.")
    else:
        r["onchain_armazenado"] = verificar_on_chain(contract, armazenado)
        r.update(status="modificado",
                 mensagem="Documento modificado após o registro: o conteúdo atual não está registrado na blockchain.")
    return r


# ==================== APOIO ÀS TELAS (Streamlit) ====================
MONGO_USUARIO_PADRAO = "admin"
MONGO_DATABASE_PADRAO = "context"
MONGO_COLECAO_PADRAO = "SaudeTeste"
MONGO_HOST_PADRAO = "cluster0.rfdha.gcp.mongodb.net"

# Situação do registro, a partir só do que está no Mongo (rápido; não consulta a blockchain)
SITUACAO_REGISTRO = {
    "celo": "✅ Registrado (Celo)",
    "legado": "📄 Registrado (outra rede)",
    "sem": "⏳ Sem registro",
}


def situacao_registro(documento):
    info = documento.get("blockchain_info") or {}
    if not info.get("document_hash"):
        return "sem"
    if (info.get("hash_scheme") == HASH_SCHEME and info.get("chain_id") == CHAIN_ID
            and str(info.get("contract_address", "")).lower() == CONTRACT_ADDRESS.lower()):
        return "celo"
    return "legado"


def mascarar_cns(cns):
    cns = str(cns or "")
    return "•" * max(len(cns) - 4, 0) + cns[-4:] if cns else "N/A"


def conexao_mongo(prefixo, titulo="📊 Conectar ao MongoDB"):
    """Mostra o formulário de conexão (se ainda não conectado) e devolve a coleção, ou None.
    Cada tela usa um prefixo próprio no session_state para não misturar conexões."""
    import streamlit as st
    from pymongo import MongoClient

    chave = f"{prefixo}_colecao"
    if st.session_state.get(chave) is not None:
        coll = st.session_state[chave]
        c1, c2 = st.columns([4, 1])
        with c1:
            st.caption(f"🟢 Conectado: `{coll.database.name}.{coll.name}`")
        with c2:
            if st.button("Desconectar", key=f"{prefixo}_desconectar", width="stretch"):
                cli = st.session_state.pop(f"{prefixo}_cliente", None)
                if cli:
                    cli.close()
                st.session_state[chave] = None
                st.rerun()
        return coll

    st.subheader(titulo)
    # clear_on_submit: a senha digitada não fica guardada no formulário depois do envio
    with st.form(f"{prefixo}_form_mongo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            usuario = st.text_input("Usuário", value=MONGO_USUARIO_PADRAO)
            database = st.text_input("Database", value=MONGO_DATABASE_PADRAO)
        with c2:
            senha = st.text_input(f"Senha MongoDB ({SENHA_DIGITADA_TAM} caracteres)", type="password",
                                  max_chars=SENHA_DIGITADA_TAM, help=AJUDA_SENHA_MONGO)
            colecao = st.text_input("Coleção", value=MONGO_COLECAO_PADRAO)
        host = st.text_input("Host/Cluster", value=MONGO_HOST_PADRAO)
        enviar = st.form_submit_button("🔌 Conectar", width="stretch")

    if enviar:
        erro = validar_senha_mongo(senha)
        if erro:
            st.error(f"⚠️ {erro}")
            return None
        try:
            with st.spinner("🔄 Conectando ao MongoDB..."):
                cli = MongoClient(build_mongo_uri(usuario, senha, host, database), serverSelectionTimeoutMS=5000)
                cli.server_info()
            st.session_state[f"{prefixo}_cliente"] = cli
            st.session_state[chave] = cli[database][colecao]
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao conectar: {e}")
    return None

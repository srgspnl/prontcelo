"""
celo_common.py - módulo compartilhado (Celo Sepolia + MongoDB)

Usado por insertreg.py e verificahash.py.
As senhas ficam em um arquivo de texto (senhas.txt), na mesma pasta dos scripts.
Ordem de busca de cada valor: variável de ambiente -> senhas.txt -> .streamlit/secrets.toml -> padrão.
"""
import os
import re
import json
import time
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

from bson.json_util import dumps as _bson_dumps, RELAXED_JSON_OPTIONS
from web3 import Web3


def _ler_arquivo_senhas():
    """Lê senhas.txt: uma configuração por linha, no formato CHAVE=valor (ou CHAVE: valor).
    Linhas em branco e iniciadas por # são ignoradas. Aspas ao redor do valor são opcionais."""
    candidatos = [os.getenv("SENHAS_FILE"), Path.cwd() / "senhas.txt",
                  Path(__file__).resolve().parent / "senhas.txt"]
    for c in candidatos:
        if not c or not Path(c).is_file():
            continue
        bruto = Path(c).read_bytes()
        try:
            texto = bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = bruto.decode("utf-16")      # Bloco de Notas às vezes salva assim
        dados = {}
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(.*)$", linha)
            if m:
                dados[m.group(1).upper()] = m.group(2).strip().strip('"').strip("'")
        return dados
    return {}


_ARQUIVO = _ler_arquivo_senhas()


def _cfg(nomes, padrao=None):
    """Aceita um nome ou uma tupla de nomes equivalentes (apelidos aceitos no senhas.txt)."""
    for nome in ((nomes,) if isinstance(nomes, str) else nomes):
        valor = os.getenv(nome) or _ARQUIVO.get(nome)
        if valor:
            return valor
    try:
        import streamlit as st
        for nome in ((nomes,) if isinstance(nomes, str) else nomes):
            v = st.secrets.get(nome)
            if v:
                return v
    except Exception:
        pass
    return padrao


# ==================== REDE / CONTRATO ====================
NETWORK_NAME = "Celo Sepolia Testnet"
CHAIN_ID = 11142220
RPC_URL = _cfg("CELO_RPC_URL", "https://forno.celo-sepolia.celo-testnet.org")
EXPLORER_URL = "https://celo-sepolia.blockscout.com"
FAUCET_URL = "https://faucet.celo.org/celo-sepolia"
CONTRACT_ADDRESS = Web3.to_checksum_address(
    _cfg("CELO_CONTRACT_ADDRESS", "0xfe35A002800711b3F969fE286d0370335bc73852").lower()
)
PRIVATE_KEY_ENV = _cfg(("CELO_PRIVATE_KEY", "CHAVE_PRIVADA", "PRIVATE_KEY"), "")   # evita digitar a chave
MONGO_URI_ENV = _cfg("MONGO_URI", "")                                              # URI completa (opcional)
MONGO_SENHA_ARQ = _cfg(("MONGO_SENHA", "SENHA_MONGODB", "SENHA_MONGO"), "")        # senha real, sem truncar
MONGO_USUARIO_ARQ = _cfg(("MONGO_USUARIO", "USUARIO_MONGODB"), "")
MONGO_HOST_ARQ = _cfg(("MONGO_HOST", "HOST_MONGODB"), "")
MONGO_PRONTA = bool(MONGO_URI_ENV or MONGO_SENHA_ARQ)   # True: as telas dispensam digitar a senha do Mongo

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
    """Prioridade: MONGO_URI do senhas.txt; depois MONGO_SENHA do senhas.txt (senha real, sem cortar);
    por fim a convenção dos outros scripts: o usuário digita 12 caracteres e só os 8 primeiros são usados."""
    if MONGO_URI_ENV:
        return MONGO_URI_ENV
    if MONGO_SENHA_ARQ:
        return (f"mongodb+srv://{quote_plus(MONGO_USUARIO_ARQ or usuario)}:{quote_plus(MONGO_SENHA_ARQ)}"
                f"@{MONGO_HOST_ARQ or host}/{database}?retryWrites=true&w=majority")
    return (f"mongodb+srv://{quote_plus(usuario)}:{quote_plus(senha[:8])}"
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
def verificar_integridade(documento, contract=None):
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

    oc = verificar_on_chain(contract, calculado, tentativas=3, intervalo=1.5)
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

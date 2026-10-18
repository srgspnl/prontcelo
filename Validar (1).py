import streamlit as st
from web3 import Web3
from web3.exceptions import TransactionNotFound, BlockNotFound
import json
from datetime import datetime

import celo_common as cc

# ==================== CONFIGURAÇÃO DA PÁGINA ====================
st.set_page_config(
    page_title="Verificador Blockchain",
    page_icon="🔍",
    layout="wide"
)

# ==================== CONSTANTES ====================
CONTRACT_ADDRESS = cc.CONTRACT_ADDRESS  # Celo Sepolia (configurável no senhas.txt)

CONTRACT_ABI = [
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
    }
]

# CSS customizado
st.markdown("""
<style>
    .verification-box-success {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .verification-box-warning {
        background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .verification-box-error {
        background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .hash-display {
        font-family: monospace;
        background-color: #f5f5f5;
        padding: 12px;
        border-radius: 8px;
        word-break: break-all;
        font-size: 0.9em;
    }
    .info-card {
        background-color: #f8f9fa;
        border-left: 4px solid #2196F3;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== FUNÇÕES ====================

def normalizar_hash(hash_str):
    """
    Normaliza hash removendo 0x e espaços
    """
    if not hash_str:
        return None
    
    hash_str = hash_str.strip().lower()
    if hash_str.startswith('0x'):
        hash_str = hash_str[2:]
    
    return hash_str

def validar_hash(hash_str, nome_campo):
    """
    Valida formato do hash
    """
    if not hash_str:
        return False, f"{nome_campo} não pode estar vazio"
    
    if len(hash_str) != 64:
        return False, f"{nome_campo} deve ter 64 caracteres (tem {len(hash_str)})"
    
    try:
        int(hash_str, 16)
        return True, None
    except ValueError:
        return False, f"{nome_campo} deve conter apenas caracteres hexadecimais (0-9, a-f)"

def validar_tx_hash(tx_hash):
    """
    Valida formato do transaction hash
    """
    if not tx_hash:
        return False, "Transaction hash não pode estar vazio"
    
    if not tx_hash.startswith('0x'):
        return False, "Transaction hash deve começar com 0x"
    
    if len(tx_hash) != 66:
        return False, f"Transaction hash deve ter 66 caracteres (tem {len(tx_hash)})"
    
    try:
        int(tx_hash[2:], 16)
        return True, None
    except ValueError:
        return False, "Transaction hash deve conter apenas caracteres hexadecimais após 0x"

def verificar_hash_no_contrato(w3, contract, hash_hex):
    """
    Verifica o hash diretamente no smart contract
    """
    try:
        # leitura com repetição: o RPC público pode estar atrasado em registros recém-confirmados
        r = cc.verificar_on_chain(contract, hash_hex, tentativas=3, intervalo=1.5)
        exists, is_valid, timestamp = r["exists"], r["is_valid"], r["timestamp"]
        provider, record_type, record_id = r["provider"], r["record_type"], r["record_id"]
        
        return {
            "success": True,
            "exists": exists,
            "is_valid": is_valid,
            "timestamp": timestamp,
            "provider": provider,
            "record_type": record_type,
            "record_id": record_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def extrair_hash_do_input_data(w3, contract, input_data):
    """
    Extrai o hash dos dados de input da transação usando decode ABI
    CORRIGIDO: Usa decode_function_input para extrair corretamente
    """
    try:
        # Decodificar input data usando ABI
        func_obj, func_params = contract.decode_function_input(input_data)
        
        # Verificar se é a função registerHash
        if func_obj.fn_name == 'registerHash':
            # Extrair o hash (primeiro parâmetro)
            hash_bytes = func_params.get('_hash')
            
            if hash_bytes:
                # Converter bytes32 para hex string
                hash_hex = hash_bytes.hex().removeprefix("0x")
                
                # Extrair também outros parâmetros
                record_type = func_params.get('_recordType', '')
                record_id = func_params.get('_recordId', '')
                
                return {
                    "success": True,
                    "hash": hash_hex,
                    "record_type": record_type,
                    "record_id": record_id,
                    "function": func_obj.fn_name
                }
        
        return {
            "success": False,
            "error": f"Função chamada não é registerHash (é {func_obj.fn_name})"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def buscar_transacao_completa(w3, tx_hash):
    """
    Busca transação e receipt
    """
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        
        return {
            "success": True,
            "transaction": tx,
            "receipt": receipt
        }
    
    except TransactionNotFound:
        return {
            "success": False,
            "error": "Transação não encontrada na Celo Sepolia"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ==================== INTERFACE ====================

st.title("🔍 Verificador de Blockchain - Celo Sepolia Testnet")
st.markdown("### Sistema de Verificação de Integridade Blockchain")
st.markdown("---")

# ==================== FORMULÁRIO ====================

with st.form("verification_form"):
    st.subheader("📝 Dados para Verificação")
    
    hash_documento = st.text_input(
        "Hash do Documento (SHA-256)",
        help="Hash SHA-256 de 64 caracteres hexadecimais (com ou sem 0x)",
        placeholder="5e74faa0e8b070ee34059b9a8a5f9173ae87d22b0c1940038f209bcee1aa0a5a"
    )
    
    tx_hash = st.text_input(
        "Transaction Hash (TX Hash)",
        help="Hash da transação na Celo Sepolia (deve começar com 0x)",
        placeholder="0x1234567890abcdef..."
    )
    
    submit = st.form_submit_button("🔍 Verificar no Blockchain", use_container_width=True)

# ==================== PROCESSAMENTO ====================

if submit:
    # Normalizar inputs
    hash_documento_norm = normalizar_hash(hash_documento)
    tx_hash_norm = tx_hash.strip() if tx_hash else ""
    
    if not tx_hash_norm.startswith('0x'):
        tx_hash_norm = '0x' + tx_hash_norm
    
    # Validações
    erros = []
    
    valido, erro = validar_hash(hash_documento_norm, "Hash do documento")
    if not valido:
        erros.append(erro)
    
    valido, erro = validar_tx_hash(tx_hash_norm)
    if not valido:
        erros.append(erro)
    
    if erros:
        st.error("⚠️ **Erros de validação:**")
        for erro in erros:
            st.error(f"• {erro}")
        st.stop()
    
    st.markdown("---")
    
    # Conectar ao Web3
    try:
        with st.spinner("🔄 Conectando à Celo Sepolia Testnet..."):
            w3 = cc.get_web3()  # lança erro claro se o RPC estiver fora do ar ou na rede errada
            
            if not w3.is_connected():
                st.error("❌ Não foi possível conectar à Celo Sepolia Testnet")
                st.info("💡 Verifique sua conexão com a internet ou tente novamente.")
                st.stop()
            
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(CONTRACT_ADDRESS),
                abi=CONTRACT_ABI
            )
            
            st.success("✅ Conectado à Celo Sepolia Testnet")
    
    except Exception as e:
        st.error(f"❌ Erro ao conectar: {e}")
        st.stop()
    
    # ==================== VERIFICAÇÃO 1: SMART CONTRACT ====================
    
    st.markdown("---")
    st.subheader("🔗 Verificação no Smart Contract")
    
    with st.spinner("Consultando smart contract..."):
        resultado_contrato = verificar_hash_no_contrato(w3, contract, hash_documento_norm)
        
        if not resultado_contrato["success"]:
            st.error(f"❌ Erro ao consultar contrato: {resultado_contrato['error']}")
        elif resultado_contrato["exists"]:
            st.success("✅ Hash encontrado no smart contract!")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                status = "🟢 VÁLIDO" if resultado_contrato["is_valid"] else "🔴 INVALIDADO"
                st.metric("Status", status)
            
            with col2:
                if resultado_contrato["timestamp"] > 0:
                    dt = datetime.fromtimestamp(resultado_contrato["timestamp"])
                    st.metric("Data de Registro", dt.strftime('%d/%m/%Y'))
                    st.caption(dt.strftime('%H:%M:%S'))
                else:
                    st.metric("Data de Registro", "N/A")
            
            with col3:
                provider = resultado_contrato["provider"]
                st.metric("Provedor", provider[:10] + "...")
                st.caption(provider)
            
            # Informações adicionais
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Tipo:** {resultado_contrato['record_type']}")
            with col2:
                st.info(f"**Record ID:** {resultado_contrato['record_id']}")
            
            with st.expander("📋 Detalhes Completos do Contrato"):
                st.json(resultado_contrato)
        else:
            st.warning("⚠️ Hash NÃO encontrado no smart contract")
            st.info("Isso significa que este hash nunca foi registrado neste contrato ou foi registrado em outro contrato.")
    
    # ==================== VERIFICAÇÃO 2: TRANSAÇÃO ====================
    
    st.markdown("---")
    st.subheader("📡 Verificação da Transação")
    
    with st.spinner("Buscando transação no blockchain..."):
        resultado_tx = buscar_transacao_completa(w3, tx_hash_norm)
        
        if not resultado_tx["success"]:
            st.error(f"❌ {resultado_tx['error']}")
        else:
            tx = resultado_tx["transaction"]
            receipt = resultado_tx["receipt"]
            
            st.success("✅ Transação encontrada!")
            
            # Verificar se a transação é para o contrato correto
            to_address = tx.get('to', '').lower() if tx.get('to') else ''
            contract_address_lower = CONTRACT_ADDRESS.lower()
            
            if to_address != contract_address_lower:
                st.warning(f"⚠️ **ATENÇÃO**: Esta transação foi enviada para outro endereço!")
                st.error(f"**Esperado:** {CONTRACT_ADDRESS}")
                st.error(f"**Recebido:** {tx.get('to', 'N/A')}")
                st.info("💡 Esta transação não é para o contrato de saúde esperado.")
            else:
                st.success(f"✅ Transação enviada para o contrato correto: {CONTRACT_ADDRESS}")
            
            # Informações da transação
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Bloco", f"#{tx.blockNumber}")
            
            with col2:
                st.metric("From", tx['from'][:10] + "...")
                st.caption(tx['from'])
            
            with col3:
                status = receipt.get("status", 0)
                st.metric("Status TX", "✅ Sucesso" if status == 1 else "❌ Falhou")
            
            # Informações de gas
            col1, col2 = st.columns(2)
            with col1:
                gas_used = receipt.get("gasUsed", 0)
                st.metric("Gas Usado", f"{gas_used:,}")
            with col2:
                gas_price = receipt.get("effectiveGasPrice", 0)
                gas_price_gwei = w3.from_wei(gas_price, 'gwei')
                st.metric("Gas Price", f"{gas_price_gwei:.2f} Gwei")
            
            # Extrair hash do input data
            st.markdown("---")
            st.subheader("🔐 Análise dos Dados da Transação")
            
            input_data = tx.get("input", "")
            
            with st.spinner("Decodificando input data..."):
                resultado_extracao = extrair_hash_do_input_data(w3, contract, input_data)
                
                if not resultado_extracao["success"]:
                    st.error(f"❌ Erro ao extrair hash: {resultado_extracao['error']}")
                else:
                    hash_extraido = resultado_extracao["hash"]
                    
                    st.success(f"✅ Função chamada: **{resultado_extracao['function']}**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Hash Informado:**")
                        st.code(hash_documento_norm, language=None)
                    
                    with col2:
                        st.markdown("**Hash Extraído da TX:**")
                        st.code(hash_extraido, language=None)
                    
                    # Comparar hashes
                    if hash_documento_norm == hash_extraido:
                        st.markdown("""
                        <div class="verification-box-success">
                            <h2 style="margin: 0;">✅ HASHES CORRESPONDENTES</h2>
                            <p style="margin: 10px 0 0 0; font-size: 1.2em;">Perfeito! Os hashes são idênticos</p>
                            <p style="margin: 5px 0 0 0;">O hash do documento está registrado nesta transação</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="verification-box-warning">
                            <h2 style="margin: 0;">⚠️ HASHES DIFERENTES</h2>
                            <p style="margin: 10px 0 0 0; font-size: 1.2em;">Os hashes não correspondem</p>
                            <p style="margin: 5px 0 0 0;">O hash informado NÃO foi registrado nesta transação</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Mostrar parâmetros adicionais
                    with st.expander("📋 Parâmetros Completos da Transação"):
                        st.json({
                            "function": resultado_extracao["function"],
                            "hash": resultado_extracao["hash"],
                            "record_type": resultado_extracao["record_type"],
                            "record_id": resultado_extracao["record_id"]
                        })
            
            # Mostrar input data bruto
            with st.expander("🔍 Input Data Bruto (Hexadecimal)"):
                if hasattr(input_data, 'hex'):
                    st.code(input_data.hex(), language=None)
                else:
                    st.code(str(input_data), language=None)
    
    # ==================== RESUMO FINAL ====================
    
    st.markdown("---")
    st.subheader("📊 Resumo da Verificação")
    
    # Determinar resultado final
    hash_no_contrato = resultado_contrato.get("success") and resultado_contrato.get("exists", False)
    hash_valido_contrato = hash_no_contrato and resultado_contrato.get("is_valid", False)
    
    tx_encontrada = resultado_tx.get("success", False)
    hash_na_transacao = False
    tx_para_contrato_correto = False
    
    if tx_encontrada:
        tx_para_contrato_correto = to_address == contract_address_lower
        if resultado_extracao.get("success"):
            hash_na_transacao = (hash_documento_norm == resultado_extracao.get("hash", ""))
    
    # Cenários
    if hash_no_contrato and hash_valido_contrato and hash_na_transacao and tx_para_contrato_correto:
        st.markdown("""
        <div class="info-card" style="border-left-color: #4CAF50;">
            <h4>🎉 Verificação Completa e Bem-Sucedida</h4>
            <ul>
                <li>✅ Hash encontrado e válido no smart contract</li>
                <li>✅ Hash confirmado na transação blockchain</li>
                <li>✅ Hashes correspondem perfeitamente</li>
                <li>✅ Transação enviada para o contrato correto</li>
                <li>✅ Documento autêntico e não adulterado</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    elif hash_no_contrato and not hash_valido_contrato:
        st.markdown("""
        <div class="info-card" style="border-left-color: #f44336;">
            <h4>🔴 Hash Invalidado</h4>
            <ul>
                <li>⚠️ Hash foi encontrado no contrato</li>
                <li>❌ Mas foi INVALIDADO posteriormente</li>
                <li>⚠️ Este documento não é mais considerado válido</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    elif hash_no_contrato and hash_na_transacao and not tx_para_contrato_correto:
        st.markdown("""
        <div class="info-card" style="border-left-color: #FF9800;">
            <h4>⚠️ Transação Para Contrato Incorreto</h4>
            <ul>
                <li>✅ Hash encontrado no smart contract</li>
                <li>✅ Hash presente na transação</li>
                <li>❌ Transação foi para um endereço diferente</li>
                <li>💡 Verifique se o transaction hash está correto</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    elif hash_no_contrato and not hash_na_transacao:
        st.markdown("""
        <div class="info-card" style="border-left-color: #FF9800;">
            <h4>⚠️ Hash em Outra Transação</h4>
            <ul>
                <li>✅ Hash encontrado no smart contract</li>
                <li>❌ Hash não corresponde à transação informada</li>
                <li>💡 O hash pode ter sido registrado em outra transação</li>
                <li>💡 Verifique o transaction hash no MongoDB</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    elif not hash_no_contrato and hash_na_transacao:
        st.markdown("""
        <div class="info-card" style="border-left-color: #FF9800;">
            <h4>⚠️ Transação Pode Ter Falhado</h4>
            <ul>
                <li>❌ Hash NÃO encontrado no smart contract</li>
                <li>✅ Hash presente na transação</li>
                <li>⚠️ A transação pode ter sido revertida</li>
                <li>💡 Verifique o status da transação acima</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    else:
        st.markdown("""
        <div class="info-card" style="border-left-color: #f44336;">
            <h4>❌ Verificação Falhou</h4>
            <ul>
                <li>❌ Hash NÃO encontrado no smart contract</li>
                <li>❌ Hash não corresponde à transação</li>
                <li>⚠️ Verifique se os dados informados estão corretos</li>
                <li>💡 O hash pode nunca ter sido registrado</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Link para o explorer (Blockscout)
    st.markdown("---")
    st.link_button(
        "🔗 Ver Transação Completa no Blockscout",
        cc.explorer_tx_url(tx_hash_norm),
        use_container_width=True
    )

# ==================== INSTRUÇÕES ====================

st.markdown("---")

with st.expander("ℹ️ Como Usar Este Verificador"):
    st.markdown("""
    ### 🎯 Objetivo
    
    Este sistema verifica se um hash de documento está realmente registrado no blockchain Celo Sepolia,
    fazendo uma verificação tripla:
    
    1. **No Smart Contract**: Consulta se o hash existe e está válido
    2. **Na Transação**: Verifica se a transação foi para o contrato correto
    3. **Nos Dados**: Decodifica os parâmetros para confirmar o hash exato
    
    ### 📝 Como Usar
    
    1. **Hash do Documento**: Cole o hash SHA-256 (64 caracteres)
       - Pode incluir ou não o prefixo `0x`
       - Encontrado em: `blockchain_info.document_hash` no MongoDB
    
    2. **Transaction Hash**: Cole o hash da transação (66 caracteres com 0x)
       - Encontrado em: `blockchain_info.transaction.transaction_hash` no MongoDB
    
    3. Clique em "Verificar no Blockchain"
    
    ### ✅ Resultados Possíveis
    
    - **🟢 Verificação Completa**: Tudo OK - documento autêntico
    - **🔴 Hash Invalidado**: Hash existe mas foi invalidado
    - **🟡 Verificação Parcial**: Alguma inconsistência detectada
    - **🔴 Verificação Falhou**: Hash não encontrado ou dados incorretos
    
    ### 🔍 O Que é Verificado
    
    - ✅ Existência do hash no contrato
    - ✅ Status de validade do hash
    - ✅ Correspondência dos hashes
    - ✅ Endereço de destino da transação
    - ✅ Status de confirmação da transação
    - ✅ Decodificação correta dos parâmetros
    
    ### 💡 Dicas
    
    - Se a verificação falhar, confira se copiou os valores corretos do MongoDB
    - Use o link do Blockscout para ver mais detalhes da transação
    - Hashes invalidados não são mais considerados válidos no sistema
    """)

# ==================== RODAPÉ ====================

st.markdown("---")
st.caption("🔗 Verificador Blockchain - Celo Sepolia Testnet")
st.caption("🔍 Sistema de Verificação de Integridade e Autenticidade | Versão 2.0")
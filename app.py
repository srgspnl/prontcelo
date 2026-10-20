"""
app.py - PROGRAMA DE ENTRADA do sistema de registro em blockchain (Celo Sepolia + MongoDB)

Como rodar (na pasta dos scripts):
    streamlit run app.py

O menu lateral leva às telas:
  - Início ............ menu e testes de conexão
  - Inserir ........... inserirdoc.py   (inclui novos prontuários no MongoDB)
  - Documentos ........ listadocs.py    (lista quem tem e quem não tem registro em blockchain)
  - Registrar ......... insertreg.py    (grava o hash do documento na blockchain)
  - Verificar ......... verificahash.py (confere se o documento foi alterado)

Nenhuma senha é armazenada: a senha do MongoDB (12 caracteres, só os 8 primeiros são usados)
e a chave privada da carteira são pedidas na tela sempre que forem necessárias.
"""
import streamlit as st
from web3 import Web3

import celo_common as cc

st.set_page_config(page_title="Sistema Celo - Registro e Verificação", page_icon="⛓️", layout="wide")


def pagina_inicio():
    st.title("⛓️ Sistema de Registro e Verificação de Documentos")
    st.markdown(f"MongoDB × **{cc.NETWORK_NAME}** · contrato `{cc.CONTRACT_ADDRESS}`")
    st.markdown("---")

    # ---------- menu de opções ----------
    st.subheader("📋 O que você quer fazer?")
    opcoes = [
        ("➕ Inserir documentos", "Inclui novos prontuários no MongoDB (formulário, arquivo .json ou JSON colado), "
         "com status Pendente de Validação.", PAG_INSERIR, "Abrir inclusão"),
        ("📚 Documentos", "Lista os documentos e mostra quem tem e quem não tem registro em blockchain. "
         "Opcionalmente confere a integridade de cada um.", PAG_LISTAR, "Abrir lista"),
        ("🔗 Registrar documento", "Calcula o hash de um documento do MongoDB e grava na blockchain. "
         "Pede a chave privada de uma carteira autorizada.", PAG_REGISTRAR, "Abrir registro"),
        ("🔍 Verificar integridade", "Recalcula o hash do documento atual e confere na blockchain se ele "
         "foi alterado. Somente leitura, não precisa de chave.", PAG_VERIFICAR, "Abrir verificador"),
    ]
    for i in range(0, len(opcoes), 2):
        cols = st.columns(2)
        for col, (titulo, texto, pagina, rotulo) in zip(cols, opcoes[i:i + 2]):
            with col:
                with st.container(border=True):
                    st.markdown(f"### {titulo}")
                    st.write(texto)
                    st.page_link(pagina, label=rotulo, icon=titulo.split()[0])

    st.markdown("---")

    # ---------- como as senhas funcionam ----------
    st.subheader("🔑 Senhas")
    st.info(
        "Nenhuma senha fica armazenada no sistema. Elas são pedidas na tela sempre que forem necessárias:\n\n"
        f"- **Senha do MongoDB:** digite {cc.SENHA_DIGITADA_TAM} caracteres. O sistema usa só os "
        f"{cc.SENHA_REAL_TAM} primeiros; os {cc.SENHA_DIGITADA_TAM - cc.SENHA_REAL_TAM} últimos são "
        "preenchimento (ofuscamento).\n"
        "- **Chave privada da carteira:** pedida apenas na tela “Registrar documento”, a cada registro."
    )

    st.markdown("---")

    # ---------- testes de conexão ----------
    st.subheader("🧪 Testar conexões")
    t1, t2 = st.columns(2)
    with t1:
        with st.form("ini_teste_celo"):
            st.markdown("**Celo Sepolia** (somente leitura)")
            endereco = st.text_input("Endereço público da carteira (opcional)", placeholder="0x...",
                                     help="Mostra saldo e se a carteira está autorizada. "
                                          "É o endereço público, não a chave privada.")
            testar_celo = st.form_submit_button("Testar Celo Sepolia", width="stretch")
        if testar_celo:
            try:
                with st.spinner("Conectando..."):
                    w3 = cc.get_web3()
                    bloco = w3.eth.block_number
                st.success(f"✅ Celo Sepolia OK · bloco atual #{bloco}")
                if endereco.strip():
                    conta = Web3.to_checksum_address(endereco.strip())
                    saldo = w3.from_wei(w3.eth.get_balance(conta), "ether")
                    autorizada = cc.get_contract(w3).functions.isProviderAuthorized(conta).call()
                    st.info(f"Carteira {conta} · {saldo:.4f} CELO · "
                            + ("autorizada ✅" if autorizada else "NÃO autorizada ❌"))
            except Exception as e:
                st.error(f"❌ {e}")
    with t2:
        with st.form("ini_teste_mongo", clear_on_submit=True):
            st.markdown("**MongoDB**")
            c1, c2 = st.columns(2)
            with c1:
                usuario = st.text_input("Usuário", value=cc.MONGO_USUARIO_PADRAO)
            with c2:
                senha = st.text_input(f"Senha ({cc.SENHA_DIGITADA_TAM} caracteres)", type="password",
                                      max_chars=cc.SENHA_DIGITADA_TAM, help=cc.AJUDA_SENHA_MONGO)
            host = st.text_input("Host/Cluster", value=cc.MONGO_HOST_PADRAO)
            testar_mongo = st.form_submit_button("Testar MongoDB", width="stretch")
        if testar_mongo:
            erro = cc.validar_senha_mongo(senha)
            if erro:
                st.error(f"⚠️ {erro}")
            else:
                try:
                    from pymongo import MongoClient
                    with st.spinner("Conectando..."):
                        cli = MongoClient(cc.build_mongo_uri(usuario, senha, host, cc.MONGO_DATABASE_PADRAO),
                                          serverSelectionTimeoutMS=5000)
                        cli.server_info()
                        cli.close()
                    st.success("✅ MongoDB OK")
                except Exception as e:
                    st.error(f"❌ {e}")

    st.markdown("---")
    st.caption("Para iniciar localmente: abra o terminal na pasta dos scripts e rode  `streamlit run app.py`")


PAG_INICIO = st.Page(pagina_inicio, title="Início", icon="🏠", default=True)
PAG_INSERIR = st.Page("inserirdoc.py", title="Inserir documentos", icon="➕")
PAG_LISTAR = st.Page("listadocs.py", title="Documentos", icon="📚")
PAG_REGISTRAR = st.Page("insertreg.py", title="Registrar documento", icon="🔗")
PAG_VERIFICAR = st.Page("verificahash.py", title="Verificar integridade", icon="🔍")

with st.sidebar:
    st.markdown("### ⛓️ Sistema Celo")
    st.caption("🔒 Nenhuma senha é armazenada: elas são pedidas em cada tela.")

st.navigation([PAG_INICIO, PAG_INSERIR, PAG_LISTAR, PAG_REGISTRAR, PAG_VERIFICAR]).run()

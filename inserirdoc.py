"""
inserirdoc.py - inclusão de novos documentos (prontuários) no MongoDB

Três formas de incluir:
  1. Formulário (um atendimento por vez, no formato do prontuario_modelo.json)
  2. Arquivo .json (um objeto ou uma lista de objetos, como prontuarios_exemplo_10.json)
  3. Colar o JSON na tela

Todo documento novo entra com statusRegistroBlockchain = "Pendente de Validação" e SEM blockchain_info.
O registro na blockchain é feito depois, na tela "Registrar documento".
"""
import json
from datetime import datetime, time as dtime, timezone

import streamlit as st

import celo_common as cc

cc.configurar_pagina("Inserir Documentos - Celo", "➕")

OBRIGATORIOS = ("idAtendimento", "cnsPaciente", "dataHoraAtendimento", "tipoAtendimento")
TIPOS = ["Vacinação", "Consulta Pré-natal", "Consulta Pediátrica", "Consulta Hipertensão", "Consulta Diabetes",
         "Consulta Odontológica", "Consulta Saúde Mental", "Consulta Geriátrica", "Consulta Puericultura", "Outro"]


# ==================== VALIDAÇÃO ====================
def preparar(doc):
    """Valida e normaliza um documento. Devolve (documento, lista_de_erros)."""
    if not isinstance(doc, dict):
        return None, ["não é um objeto JSON"]
    doc = json.loads(json.dumps(doc))          # cópia independente
    erros = [f"campo obrigatório ausente: {c}" for c in OBRIGATORIOS if not str(doc.get(c) or "").strip()]
    if doc.get("blockchain_info"):
        erros.append("já contém blockchain_info (documento novo não pode vir registrado)")
    cns = str(doc.get("cnsPaciente") or "")
    if cns and (not cns.isdigit() or len(cns) != 15):
        erros.append("cnsPaciente deve ter 15 dígitos")
    doc.pop("_id", None)                       # o Mongo gera um _id novo
    doc.pop("blockchain_info", None)
    dcg = doc.get("dadosClinicosGerais")
    if not isinstance(dcg, dict):
        dcg = doc["dadosClinicosGerais"] = {}
    dcg["statusRegistroBlockchain"] = cc.STATUS_PENDENTE
    return doc, erros


def inserir(coll, docs):
    """Valida tudo, recusa idAtendimento repetido (no lote ou já no banco) e insere os válidos."""
    validos, recusados = [], []
    ids_lote = set()
    existentes = {d["idAtendimento"] for d in coll.find(
        {"idAtendimento": {"$in": [str(d.get("idAtendimento")) for d in docs if isinstance(d, dict)]}},
        {"idAtendimento": 1})}
    for i, bruto in enumerate(docs, start=1):
        doc, erros = preparar(bruto)
        ida = doc.get("idAtendimento") if doc else None
        if ida in existentes:
            erros.append("idAtendimento já existe no banco")
        elif ida in ids_lote:
            erros.append("idAtendimento repetido neste lote")
        if erros:
            recusados.append({"Nº": i, "idAtendimento": ida or "-", "Motivo": "; ".join(erros)})
        else:
            ids_lote.add(ida)
            validos.append(doc)

    inseridos = []
    if validos:
        res = coll.insert_many(validos)
        inseridos = [{"idAtendimento": d["idAtendimento"], "_id (ObjectId)": str(oid),
                      "Tipo": d.get("tipoAtendimento", "")} for d, oid in zip(validos, res.inserted_ids)]
    return inseridos, recusados


def mostrar_resultado(inseridos, recusados):
    if inseridos:
        st.success(f"✅ {len(inseridos)} documento(s) inserido(s) com status “{cc.STATUS_PENDENTE}”.")
        st.dataframe(inseridos, hide_index=True, width="stretch")
        st.caption("Copie o _id para registrar o documento na blockchain (tela “Registrar documento”).")
    if recusados:
        st.error(f"❌ {len(recusados)} documento(s) recusado(s):")
        st.dataframe(recusados, hide_index=True, width="stretch")


def ler_json(texto):
    dados = json.loads(texto)
    return dados if isinstance(dados, list) else [dados]


def texto_para_dict(texto):
    """'lote=X; via=Y' -> {'lote': 'X', 'via': 'Y'}. Aceita também um JSON de objeto."""
    texto = (texto or "").strip()
    if not texto:
        return {}
    if texto.startswith("{"):
        return json.loads(texto)
    saida = {}
    for parte in texto.split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            saida[k.strip()] = v.strip()
    return saida


# ==================== INTERFACE ====================
st.title("➕ Inserir Novos Documentos")
st.markdown("Inclui prontuários no MongoDB com status **Pendente de Validação**, prontos para registro na blockchain.")
st.markdown("---")

coll = cc.conexao_mongo("ins")
if coll is None:
    st.stop()

aba_form, aba_arquivo, aba_colar = st.tabs(["📝 Formulário", "📁 Arquivo .json", "📋 Colar JSON"])

# ---------- 1. formulário ----------
with aba_form:
    with st.form("ins_formulario", clear_on_submit=False):
        st.markdown("#### Atendimento")
        c1, c2, c3 = st.columns(3)
        with c1:
            id_atend = st.text_input("ID do atendimento *",
                                     value=f"ATND-{datetime.now():%Y%m%d}-", help="Ex.: ATND-20261018-011")
            tipo = st.selectbox("Tipo de atendimento *", TIPOS)
        with c2:
            cns = st.text_input("CNS do paciente * (15 dígitos)", max_chars=15)
            data = st.date_input("Data *", value=datetime.now().date(), format="DD/MM/YYYY")
        with c3:
            hora = st.time_input("Hora *", value=dtime(9, 0), step=300)
            st.caption("A hora é gravada em UTC, como no modelo.")

        st.markdown("#### Unidade e profissional")
        c1, c2, c3 = st.columns(3)
        with c1:
            unidade = st.text_input("Unidade de saúde", value="UBS Central")
            cnes = st.text_input("CNES", value="1000001")
        with c2:
            prof = st.text_input("Profissional")
            conselho = st.text_input("Registro no conselho", placeholder="CRM-SP 100200")
        with c3:
            funcao = st.text_input("Função", placeholder="Médico, Enfermeira...")

        st.markdown("#### Dados clínicos")
        c1, c2 = st.columns(2)
        with c1:
            motivo = st.text_area("Motivo da consulta", height=80)
            historico = st.text_area("Histórico da doença atual", height=80)
        with c2:
            cid = st.text_input("Diagnóstico (CID-10)", placeholder="Z23.5")
            conduta = st.text_area("Conduta", height=80)

        st.markdown("#### Medidas e procedimentos")
        c1, c2 = st.columns(2)
        with c1:
            peso = st.number_input("Peso (kg)", min_value=0.0, max_value=400.0, value=None, step=0.1,
                                   placeholder="em branco = não medido")
        with c2:
            altura = st.number_input("Altura (cm)", min_value=0.0, max_value=250.0, value=None, step=0.5,
                                     placeholder="em branco = não medido")
        procs = st.data_editor(
            [{"Procedimento": "", "Detalhes": ""}], num_rows="dynamic", width="stretch", key="ins_procs",
            column_config={
                "Procedimento": st.column_config.TextColumn("Procedimento", width="medium"),
                "Detalhes": st.column_config.TextColumn("Detalhes (chave=valor; chave=valor)", width="large",
                                                        help="Ex.: lote=LOTEBCG2024; via=Intradérmica"),
            })
        enviar_form = st.form_submit_button("💾 Inserir documento", width="stretch", type="primary")

    if enviar_form:
        try:
            procedimentos = [{"nome": p["Procedimento"].strip(), "detalhes": texto_para_dict(p.get("Detalhes"))}
                             for p in procs if (p.get("Procedimento") or "").strip()]
            data_hora = datetime.combine(data, hora, tzinfo=timezone.utc)
            doc = {
                "idAtendimento": id_atend.strip(),
                "cnsPaciente": cns.strip(),
                "dataHoraAtendimento": data_hora.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "tipoAtendimento": tipo,
                "unidadeSaude": {"nome": unidade.strip(), "cnes": cnes.strip()},
                "profissionalSaude": {"nome": prof.strip(), "registroConselho": conselho.strip(),
                                      "funcao": funcao.strip()},
                "dadosClinicosGerais": {"motivoConsulta": motivo.strip(), "historicoDoencaAtual": historico.strip(),
                                        "diagnosticoCID10": cid.strip().upper(), "conduta": conduta.strip()},
                "dadosEspecificosProcedimento": {
                    "medidasAntropometricas": {"pesoKg": peso, "alturaCm": altura},
                    "procedimentosRealizados": procedimentos,
                },
            }
            if id_atend.strip().endswith("-"):
                st.error("⚠️ Complete o ID do atendimento (ex.: ATND-20261018-011).")
            else:
                mostrar_resultado(*inserir(coll, [doc]))
        except json.JSONDecodeError as e:
            st.error(f"❌ Detalhes de procedimento com JSON inválido: {e}")
        except Exception as e:
            st.error(f"❌ Erro: {e}")

# ---------- 2. arquivo ----------
with aba_arquivo:
    st.write("Envie um arquivo com **um documento** (como o prontuario_modelo.json) "
             "ou uma **lista de documentos** (como o prontuarios_exemplo_10.json).")
    arq = st.file_uploader("Arquivo .json", type=["json"], key="ins_arquivo")
    if arq is not None:
        try:
            docs = ler_json(arq.getvalue().decode("utf-8-sig"))
            st.info(f"📄 {len(docs)} documento(s) no arquivo.")
            st.dataframe([{"idAtendimento": d.get("idAtendimento"), "Tipo": d.get("tipoAtendimento"),
                           "Data": d.get("dataHoraAtendimento"), "CNS": cc.mascarar_cns(d.get("cnsPaciente"))}
                          for d in docs if isinstance(d, dict)], hide_index=True, width="stretch")
            if st.button(f"💾 Inserir {len(docs)} documento(s)", type="primary", key="ins_btn_arquivo"):
                mostrar_resultado(*inserir(coll, docs))
        except Exception as e:
            st.error(f"❌ Arquivo inválido: {e}")

# ---------- 3. colar ----------
with aba_colar:
    with st.form("ins_colar"):
        texto = st.text_area("JSON (um objeto ou uma lista)", height=300,
                             placeholder='{\n  "idAtendimento": "ATND-20261018-011",\n  ...\n}')
        enviar_colar = st.form_submit_button("💾 Inserir", width="stretch", type="primary")
    if enviar_colar:
        try:
            mostrar_resultado(*inserir(coll, ler_json(texto)))
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON inválido: {e}")
        except Exception as e:
            st.error(f"❌ Erro: {e}")

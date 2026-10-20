# Sistema Celo – Registro e Verificação de Documentos

Aplicação Streamlit que registra o hash de documentos do MongoDB na Celo Sepolia e verifica a integridade deles.

## Senhas: nada é armazenado

O sistema não usa `senhas.txt`, *Secrets* do Streamlit nem variáveis de ambiente. As senhas são pedidas na tela sempre que forem necessárias:

- **Senha do MongoDB (ofuscamento):** o usuário digita **12 caracteres** e o código usa só os **8 primeiros**. Os 4 últimos são preenchimento. O campo aceita no máximo 12 caracteres e recusa qualquer outro tamanho. Ela é pedida a cada conexão.
- **Chave privada da carteira:** pedida na tela "Registrar documento", a cada registro. Precisa ter 64 caracteres hexadecimais, com ou sem `0x`.

Os formulários se limpam depois do envio. A conexão com o MongoDB fica só na memória da sessão e é descartada no botão "Desconectar" ou quando a sessão termina.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar no Streamlit Community Cloud

1. Envie esta pasta para um repositório no GitHub.
2. Em share.streamlit.io, clique em **Create app**, escolha o repositório e a branch, e informe `app.py` como *Main file path*.
3. Não é preciso configurar *Secrets*.
4. No MongoDB Atlas, em **Network Access**, libere o acesso do Streamlit Cloud. Sem isso, a conexão expira com *timeout*.
5. Clique em **Deploy**. Depois disso, cada `git push` na branch atualiza o app sozinho.

Na nuvem, o app conversa com o servidor do Streamlit Cloud, então a senha digitada passa por ele, protegida por HTTPS.

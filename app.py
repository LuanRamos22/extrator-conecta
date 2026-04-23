import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import os
from datetime import datetime
import io

# Configuração visual personalizada (Mudei para layout "wide" para caber mais coisas)
st.set_page_config(page_title="Extrator de Faturas", page_icon="⚡", layout="wide")

# Estilo CSS Avançado (Fundo Tech Escuro e Efeito Vidro)
st.markdown("""
    <style>
    /* 1. Fundo da tela */
    .stApp {
        /* Para usar a sua imagem exata, recomendo subir ela no site ImgBB.com e colar o link direto aqui */
        background-image: url("https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }

    /* Deixar o cabeçalho invisível para não cortar a imagem */
    header { background-color: transparent !important; }

    /* 2. Container principal com leve transparência para ver o fundo */
    .block-container {
        background: rgba(10, 20, 35, 0.85); /* Azul muito escuro e transparente */
        border-radius: 15px;
        padding: 2rem 3rem;
        margin-top: 3rem;
    }

    /* 3. Textos em branco */
    h1, h2, h3, h4, p, label {
        color: #ffffff !important;
    }

    /* 4. CONSERTANDO O UPLOADER (Fundo escuro, texto branco e borda amarela) */
    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(0, 0, 0, 0.5) !important;
        border: 2px dashed #ffcc00 !important;
        border-radius: 10px;
    }
    
    /* Força tudo dentro do uploader a ficar visível */
    [data-testid="stFileUploadDropzone"] * {
        color: #ffffff !important;
    }

    /* 5. Barra Lateral Escura */
    [data-testid="stSidebar"] {
        background-color: rgba(5, 10, 20, 0.95) !important;
        border-right: 1px solid #ffcc00;
    }

    /* 6. Botão Amarelo */
    .stButton>button {
        background-color: #ffcc00;
        color: black !important;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #e6b800;
    }
    </style>
    """, unsafe_allow_html=True)



# Cabeçalho Limpo e Direto
st.title("Extrator de Faturas")

st.markdown("---")

st.subheader("Extração automática de Consumo e Demanda (Ponta/Fora de Ponta)")

# 1. Coloque sua chave de API aqui (agora protegida no Streamlit)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo = genai.GenerativeModel('gemini-2.5-flash')


# Função que faz o trabalho pesado (Cérebro)
import time # Adicionamos o import do tempo aqui em cima da função!

# Função que faz o trabalho pesado (Cérebro)
def extrair_dados_completos(caminho_pdf):
    arquivo_ia = genai.upload_file(caminho_pdf)
    
    prompt_historico = """
    Analise a tabela "CONSUMO DOS ÚLTIMOS 13 MESES". Extraia TODOS os meses.
    - mes_referencia
    - consumo_ponta_kwh (da coluna CONSUMO FATURADO sob PONTA)
    - demanda_ponta_kw (da coluna DEMANDA MEDIDA sob PONTA)
    - consumo_fora_ponta_kwh (da coluna CONSUMO FATURADO sob FORA DE PONTA)
    - demanda_fora_ponta_kw (da coluna DEMANDA MEDIDA sob FORA DE PONTA)
    NUNCA some os valores. Se vazio, use 0.0. Retorne APENAS o JSON puro.
    """

    prompt_atual = """
    Analise a tabela "Itens da Fatura". Extraia apenas as linhas com as grandezas de Consumo e Demanda na Ponta e Fora Ponta.
    Ignore tributos e impostos (PIS, COFINS, ICMS, Fisco).
    Retorne JSON: [{"item": "Nome", "quantidade": 0.0, "valor_total_rs": 0.0}]
    """

    # --- INÍCIO DO "DISJUNTOR" CONTRA O ERRO 429 ---
    try:
        res_hist = modelo.generate_content([arquivo_ia, prompt_historico])
        
        time.sleep(5) # Pausa de 5 segundos para o Google não bloquear
        
        res_atual = modelo.generate_content([arquivo_ia, prompt_atual])
        
    except Exception as erro:
        if "429" in str(erro):
            st.warning("⏳ Limite gratuito atingido! O Google pede um respiro. Aguarde 1 minuto e tente novamente.")
        else:
            st.error(f"❌ Ocorreu um erro na conexão com a IA: {erro}")
        return None, None
    # --- FIM DO DISJUNTOR ---

    def limpar_json(texto):
        return json.loads(texto.strip().replace("```json", "").replace("```", ""))

    try:
        df_historico = pd.DataFrame(limpar_json(res_hist.text))
        df_atual = pd.DataFrame(limpar_json(res_atual.text))
        return df_historico, df_atual
    except Exception as e:
        return None, None

# ==========================================
# INTERFACE GRÁFICA (A mágica do Drag and Drop)
# ==========================================

# Área para arrastar o PDF
arquivo_anexado = st.file_uploader("Arraste ou selecione a fatura em PDF", type="pdf")

if arquivo_anexado is not None:
    if st.button("Analisar Fatura"):
        with st.spinner("A Inteligência Artificial está lendo a fatura..."):
            
            # Salva o arquivo temporariamente para a IA poder ler
            caminho_temp = "fatura_temp.pdf"
            with open(caminho_temp, "wb") as f:
                f.write(arquivo_anexado.getbuffer())
            
            # Chama a IA
            df_hist, df_atual = extrair_dados_completos(caminho_temp)
            
            if df_hist is not None:
                st.success("✅ Fatura processada com sucesso!")
                
                # Prepara o Excel na memória (sem salvar sujo no PC)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_hist.to_excel(writer, sheet_name='Historico_13_Meses', index=False)
                    df_atual.to_excel(writer, sheet_name='Fatura_Atual', index=False)
                
                # Gera o botão de Download
                agora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                nome_arquivo = f"Dados_Fatura_{agora}.xlsx"
                
                st.download_button(
                    label="⬇️ Baixar Planilha Excel",
                    data=buffer.getvalue(),
                    file_name=nome_arquivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Mostra uma prévia na tela
                st.write("👀 Pré-visualização do Histórico:")
                st.dataframe(df_hist)
            else:
                st.error("Erro ao ler o documento. Tente novamente.")
            
            # Limpa o arquivo temporário
            if os.path.exists(caminho_temp):
                os.remove(caminho_temp)
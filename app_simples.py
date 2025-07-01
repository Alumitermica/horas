import streamlit as st
import pandas as pd

st.title("⏰ Teste da Aplicação de Horas")

st.write("Se vês esta mensagem, o Streamlit está a funcionar!")

# Teste básico de upload
uploaded_file = st.file_uploader("Teste de Upload CSV", type=['csv'])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.write("CSV carregado com sucesso!")
        st.write(f"Número de linhas: {len(df)}")
        st.dataframe(df.head())
    except Exception as e:
        st.error(f"Erro: {e}")

st.success("Aplicação básica a funcionar!") 
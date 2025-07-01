import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
from utils.csv_processor import CSVProcessor
from utils.rules_engine import RulesEngine
from utils.report_generator import ReportGenerator

def format_timedelta_to_hhmm(td):
    """Formats a Timedelta object into a HH:MM string."""
    if pd.isnull(td) or td.total_seconds() == 0:
        return "00:00"
    
    total_seconds = int(td.total_seconds())
    sign = '-' if total_seconds < 0 else ''
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{sign}{hours:02d}:{minutes:02d}"

def calculate_legacy_metrics(df):
    """Calcula métricas de compatibilidade com a versão anterior da aplicação."""
    if df.empty:
        return df
    
    # Objetivo padrão de 8 horas
    objetivo_td = pd.Timedelta(hours=8)
    
    # Renomear colunas para compatibilidade
    df['total_trabalho_calc'] = df['total_trabalho']
    df['total_intervalo_calc'] = df['total_pausas']
    df['horas_efetivas_td'] = df['total_trabalho']
    
    # Inicializar colunas
    df['falta_td'] = pd.Timedelta(0)
    df['extra_td'] = pd.Timedelta(0)
    
    # Reset horas efetivas para tipos que não são de trabalho
    tipos_nao_trabalho = ['Falta', 'Férias', 'Folga', 'Feriado', 'Fim de semana']
    df.loc[df['Tipo'].isin(tipos_nao_trabalho), 'horas_efetivas_td'] = pd.Timedelta(0)
    
    # Calcular faltas e extras para dias de trabalho
    dias_de_trabalho_mask = df['Tipo'].isin(['Normal', 'Falta parcial', 'Com extra'])
    df.loc[dias_de_trabalho_mask, 'falta_td'] = (objetivo_td - df.loc[dias_de_trabalho_mask, 'horas_efetivas_td']).apply(lambda x: max(x, pd.Timedelta(0)))
    df.loc[dias_de_trabalho_mask, 'extra_td'] = (df.loc[dias_de_trabalho_mask, 'horas_efetivas_td'] - objetivo_td).apply(lambda x: max(x, pd.Timedelta(0)))
    
    # Faltas totais - apenas para dias marcados como "Falta"
    falta_total_mask = df['Tipo'] == 'Falta'
    df.loc[falta_total_mask, 'falta_td'] = objetivo_td
    
    # Garantir que férias, folgas, feriados não têm faltas nem extras
    tipos_sem_falta = ['Férias', 'Folga', 'Feriado', 'Fim de semana']
    df.loc[df['Tipo'].isin(tipos_sem_falta), 'falta_td'] = pd.Timedelta(0)
    df.loc[df['Tipo'].isin(tipos_sem_falta), 'extra_td'] = pd.Timedelta(0)
    
    # Versão numérica para compatibilidade
    df['horas_efetivas_num'] = df['horas_efetivas_td'].dt.total_seconds() / 3600
    df['cumpriu_horario'] = df['horas_efetivas_num'] >= 8.0
    df['dia_trabalho'] = df['Tipo'].isin(['Normal', 'Falta parcial', 'Com extra'])
    
    # Extrair primeiro E1 e último S
    def clean_time_simple(time_str):
        if not time_str or pd.isna(time_str) or time_str == '00:00':
            return None
        return str(time_str).strip()
    
    df['primeiro_e1'] = df['E1'].apply(clean_time_simple)
    
    # Encontrar último S válido
    s_cols = [col for col in ['S4', 'S3', 'S2', 'S1'] if col in df.columns]
    def get_last_valid_time(row):
        for col in s_cols:
            time_val = clean_time_simple(row[col])
            if time_val:
                return time_val
        return None
    
    df['ultimo_s'] = df[s_cols].apply(get_last_valid_time, axis=1)
    
    return df

# Configuração da página
st.set_page_config(
    page_title="Análise de Horas de Trabalho",
    page_icon="⏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("⏰ Análise de Horas de Trabalho")
st.markdown("---")

# Sidebar para configurações
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Seleção de setor/regras
    setor_options = ["Produção", "Administrativo", "Vendas", "Logística", "Personalizado"]
    setor_selecionado = st.selectbox("Selecione o Setor:", setor_options)
    
    # Upload do arquivo CSV
    st.header("📁 Upload do CSV")
    uploaded_file = st.file_uploader(
        "Escolha o arquivo CSV com as horas de trabalho",
        type=['csv'],
        help="Faça upload do arquivo CSV exportado do sistema de ponto",
        # Clear state on new upload
        on_change=lambda: st.session_state.clear() if 'processed_data' in st.session_state else None
    )

def setup_session_state():
    """Initializes session state variables."""
    if 'processed_data' not in st.session_state:
        st.session_state['processed_data'] = pd.DataFrame()
    if 'edited_data' not in st.session_state:
        st.session_state['edited_data'] = pd.DataFrame()

def process_data(uploaded_file):
    """Processes the uploaded CSV and stores it in session state."""
    processor = CSVProcessor()
    
    with st.spinner("A processar o ficheiro CSV..."):
        # Usar o novo método melhorado que integra todos os passos
        df_unique = processor.load_and_process_csv(uploaded_file)
    
    if df_unique.empty:
        st.error("❌ Não foi possível processar o ficheiro. Verifique se o formato está correto.")
        return
    
    # Validar dados
    is_valid, message = processor.validate_data(df_unique)
    if not is_valid:
        st.warning(f"⚠️ Aviso na validação dos dados: {message}")
    else:
        st.success("✅ Ficheiro processado com sucesso!")
    
    # Mostrar estatísticas do processamento
    stats = processor.get_summary_stats(df_unique)
    if stats:
        st.info(f"📊 {stats['total_dias']} registos processados para o período {stats['periodo_analisado']}")
    
    # Add day of week and handle weekends in Portuguese
    if not df_unique.empty and 'Data' in df_unique.columns:
        days_map = {
            'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira',
            'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
        }
        df_unique['Dia da Semana'] = df_unique['Data'].dt.day_name().map(days_map)
        
        weekend_mask = df_unique['Dia da Semana'].isin(['Sábado', 'Domingo'])
        # Only set to 'Fim de semana' if the day type is something neutral like 'Folga'
        df_unique.loc[weekend_mask & df_unique['Tipo'].isin(['Folga']), 'Tipo'] = 'Fim de semana'

    # Calcular métricas compatíveis com a versão anterior
    df_unique = calculate_legacy_metrics(df_unique)

    st.session_state['processed_data'] = df_unique
    st.session_state['edited_data'] = df_unique.copy()

def show_interactive_editor(df):
    """Displays the interactive data editor with tabs for different views."""
    st.subheader("📝 Editor de Dados Interativo")
    st.info("Pode editar o 'Tipo de Dia' diretamente na tabela de resumo. As alterações serão refletidas nas análises e relatórios.")

    tab1, tab2 = st.tabs(["Visão Resumo", "Visão Detalhada (Ponto)"])
    edited_df = None

    with tab1:
        # Define columns for summary view
        summary_cols = ['Data', 'Dia da Semana', 'Tipo', 'total_trabalho_calc', 'falta_td', 'extra_td', 'horas_efetivas_td', 'cumpriu_horario', 'aviso_picagens']
        display_df_summary = df[[col for col in summary_cols if col in df.columns]].copy()
        
        # Format timedelta columns for display
        for col in ['total_trabalho_calc', 'falta_td', 'extra_td', 'horas_efetivas_td']:
            if col in display_df_summary.columns:
                display_df_summary[col] = display_df_summary[col].apply(format_timedelta_to_hhmm)

        # Configure the data editor
        edited_df = st.data_editor(
            display_df_summary,
            column_config={
                "Tipo": st.column_config.SelectboxColumn(
                    "Tipo de Dia",
                    help="Selecione o tipo de dia (ex: Normal, Falta, Férias)",
                    options=['Normal', 'Falta', 'Falta parcial', 'Folga', 'Feriado', 'Com extra', 'Fim de semana', 'Férias'],
                    required=True,
                ),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "cumpriu_horario": st.column_config.CheckboxColumn("Cumpriu Horário?", default=False),
                "aviso_picagens": st.column_config.TextColumn("Avisos", help="Avisos sobre picagens em falta ou inválidas")
            },
            use_container_width=True,
            num_rows="fixed",
            key="data_editor" 
        )

    with tab2:
        # Define columns for detailed view
        detail_cols = ['Data', 'Dia da Semana', 'Tipo', 'E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
        display_df_detail = df[[col for col in detail_cols if col in df.columns]].copy()
        st.dataframe(display_df_detail, use_container_width=True)
    
    return edited_df

# Função principal
def main():
    setup_session_state()

    if uploaded_file is not None:
        if st.session_state.processed_data.empty:
            process_data(uploaded_file)
        
        df_to_analyze = st.session_state.get('edited_data', pd.DataFrame())

        if not df_to_analyze.empty:
            # Show interactive editor and capture the returned edited dataframe
            edited_summary_df = show_interactive_editor(df_to_analyze)
            
            # If the editor returns a dataframe (i.e., we are on the summary tab and there have been edits)
            if edited_summary_df is not None:
                # Get the 'Tipo' column from the edited dataframe
                edited_tipos = edited_summary_df['Tipo']
                
                # Update the original dataframe in the session state
                if len(edited_tipos) == len(df_to_analyze):
                    df_to_analyze['Tipo'] = edited_tipos.values
                    
                    # Recalcular métricas baseadas no tipo de dia atualizado
                    df_to_analyze = calculate_legacy_metrics(df_to_analyze)
                    
                    # Persist changes back to the session state
                    st.session_state.edited_data = df_to_analyze
                    
                    # Mostrar notificação de que as alterações foram aplicadas
                    st.success("✅ Alterações aplicadas! O resumo geral foi atualizado.")

            # Verificar e mostrar avisos de picagens
            if 'aviso_picagens' in df_to_analyze.columns:
                invalid_punches = df_to_analyze[df_to_analyze['aviso_picagens'].notna() & (df_to_analyze['aviso_picagens'] != '')]
                if not invalid_punches.empty:
                    st.warning(f"⚠️ **Aviso:** Encontradas {len(invalid_punches)} linhas com problemas de picagens. Verifique a coluna 'Avisos' na tabela.")
            
            # Análises principais
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                show_summary_metrics(df_to_analyze)
            
            with col2:
                show_monthly_analysis(df_to_analyze)
            
            # Gráficos
            st.markdown("---")
            show_charts(df_to_analyze)
            
            # Análise de pontualidade
            st.markdown("---")
            show_punctuality_analysis(df_to_analyze)
            
            # Botões de download
            st.markdown("---")
            show_download_options(df_to_analyze, setor_selecionado)
        else:
            st.info("A processar o ficheiro... Se a mensagem persistir, o ficheiro pode estar vazio ou num formato inesperado.")
    else:
        # Página inicial
        st.info("👆 Faça upload de um arquivo CSV para começar a análise")
        
        # Instruções
        with st.expander("📖 Como usar esta aplicação"):
            st.markdown("""
            ### Passos para análise:
            1. **Selecione o setor** do empregado na barra lateral
            2. **Faça upload** do arquivo CSV com os dados de ponto
            3. **Visualize** as análises automáticas geradas
            4. **Configure regras** específicas se necessário
            5. **Gere relatórios** em Excel, CSV ou PDF
            
            ### Formato do CSV esperado:
            - Colunas de data, tipo de dia, entradas (E1, E2, E3, E4)
            - Saídas (S1, S2, S3, S4) e totais calculados
            - O sistema remove automaticamente linhas duplicadas
            """)

def show_summary_metrics(df):
    st.subheader("📈 Resumo Geral")
    
    # Garantir que estamos a usar os dados mais atualizados
    df_updated = df.copy()
    
    # Recalcular 'dia_trabalho' baseado no tipo de dia atualizado
    df_updated['dia_trabalho'] = df_updated['Tipo'].isin(['Normal', 'Falta parcial', 'Com extra'])
    work_days_df = df_updated[df_updated['dia_trabalho']].copy()
    
    total_days = len(df_updated)
    work_days = len(work_days_df)
    
    total_hours_td = pd.Timedelta(0)
    total_extras_td = pd.Timedelta(0)

    if work_days > 0:
        total_hours_td = work_days_df['horas_efetivas_td'].sum()
        total_extras_td = work_days_df['extra_td'].sum()

    # Separar os tipos de falta para clareza
    faltas_completas_df = df_updated[df_updated['Tipo'] == 'Falta']
    total_dias_falta = len(faltas_completas_df)
    total_horas_falta_completa = faltas_completas_df['falta_td'].sum()
    
    # Contar férias separadamente
    ferias_df = df_updated[df_updated['Tipo'] == 'Férias']
    total_dias_ferias = len(ferias_df)

    # Faltas parciais (apenas de dias de trabalho)
    parcial_mask = df_updated['Tipo'].isin(['Normal', 'Falta parcial', 'Com extra'])
    faltas_parciais_td = df_updated.loc[parcial_mask, 'falta_td'].sum()
    
    # Total de horas em falta (completas + parciais)
    total_horas_falta = total_horas_falta_completa + faltas_parciais_td

    # Mostrar métricas em 3 colunas para melhor layout
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Dias no Período", total_days)
        st.metric("Dias Efetivamente Trabalhados", work_days)
        st.metric("Dias de Férias", total_dias_ferias)
    
    with col2:
        st.metric("Total Horas Trabalhadas", format_timedelta_to_hhmm(total_hours_td))
        st.metric("Total Extras (mês)", format_timedelta_to_hhmm(total_extras_td))
    
    with col3:
        st.metric("Faltas (dias inteiros)", f"{total_dias_falta} dias")
        st.metric("Total Horas em Falta", format_timedelta_to_hhmm(total_horas_falta))

def show_monthly_analysis(df):
    st.subheader("📅 Análise Mensal")
    
    # Calcular totais por mês
    monthly_data = df.groupby(df['Data'].dt.to_period('M')).agg({
        'horas_efetivas_num': 'sum',
        'Data': 'count'
    }).round(1)
    
    monthly_data.columns = ['Horas Totais', 'Dias Trabalhados']
    st.dataframe(monthly_data)

def show_charts(df):
    st.subheader("📊 Visualizações")
    
    tab1, tab2, tab3 = st.tabs(["Horas Diárias", "Tipos de Dia", "Tendência Mensal"])
    
    with tab1:
        # Gráfico de horas por dia
        fig = px.line(df, x='Data', y='horas_efetivas_num', 
                     title="Horas Efetivas por Dia",
                     labels={'horas_efetivas_num': 'Horas', 'Data': 'Data'})
        fig.add_hline(y=8, line_dash="dash", line_color="red", 
                     annotation_text="Meta: 8h")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Distribuição por tipo de dia
        type_counts = df['Tipo'].value_counts()
        fig = px.pie(values=type_counts.values, names=type_counts.index,
                    title="Distribuição por Tipo de Dia")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Tendência mensal
        monthly_hours = df.groupby(df['Data'].dt.to_period('M'))['horas_efetivas_num'].sum()
        fig = px.bar(x=monthly_hours.index.astype(str), y=monthly_hours.values,
                    title="Total de Horas por Mês",
                    labels={'x': 'Mês', 'y': 'Horas'})
        st.plotly_chart(fig, use_container_width=True)

def show_punctuality_analysis(df):
    st.subheader("⏰ Análise de Pontualidade")
    
    # Calcular atrasos e saídas antecipadas
    work_days = df[df['Tipo'].isin(['Normal', 'Falta parcial', 'Com extra'])]
    
    if not work_days.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Entrada:**")
            late_days = len(work_days[work_days['primeiro_e1'] > '08:30'])
            st.metric("Dias com Atraso", f"{late_days}/{len(work_days)}")
            
        with col2:
            st.write("**Saída:**")
            early_days = len(work_days[work_days['ultimo_s'] < '17:30'])
            st.metric("Saídas Antecipadas", f"{early_days}/{len(work_days)}")

def show_download_options(df, setor):
    st.subheader("⬇️ Download de Relatórios")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Download Excel"):
            report_gen = ReportGenerator()
            excel_buffer = report_gen.generate_excel_report(df, setor)
            st.download_button(
                label="Baixar Relatório Excel",
                data=excel_buffer,
                file_name=f"relatorio_horas_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        if st.button("📄 Download CSV"):
            csv_buffer = ReportGenerator().generate_csv_report(df)
            st.download_button(
                label="Baixar Relatório CSV",
                data=csv_buffer,
                file_name=f"relatorio_horas_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main() 
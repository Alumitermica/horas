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
    
    # Garantir que colunas essenciais existem (fallback para CSVs mais antigos)
    if 'total_trabalho' not in df.columns or df['total_trabalho'].isna().all():
        print("⚠️ Coluna total_trabalho não encontrada ou vazia, criando fallback...")
        # Calcular total_trabalho manualmente se não existir
        df['total_trabalho'] = pd.Timedelta(0)
        for idx, row in df.iterrows():
            if row.get('picagens_validas', False):
                try:
                    # Calcular baseado nas picagens válidas
                    punches = []
                    for col in ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']:
                        if col in row and pd.notna(row[col]) and str(row[col]) not in ['00:00', '0:00', '']:
                            time_obj = pd.to_datetime(str(row[col]), format='%H:%M').time()
                            punches.append(time_obj)
                    
                    # Calcular trabalho para padrão 4 picagens (E1-S1-E2-S2)
                    if len(punches) >= 4:
                        e1, s1, e2, s2 = punches[:4]
                        # Converter para datetime para cálculo
                        base_date = pd.to_datetime('1900-01-01')
                        dt_e1 = pd.to_datetime(base_date.strftime('%Y-%m-%d') + ' ' + e1.strftime('%H:%M:%S'))
                        dt_s1 = pd.to_datetime(base_date.strftime('%Y-%m-%d') + ' ' + s1.strftime('%H:%M:%S'))
                        dt_e2 = pd.to_datetime(base_date.strftime('%Y-%m-%d') + ' ' + e2.strftime('%H:%M:%S'))
                        dt_s2 = pd.to_datetime(base_date.strftime('%Y-%m-%d') + ' ' + s2.strftime('%H:%M:%S'))
                        
                        # Manhã: E1 até S1, Tarde: E2 até S2
                        manha = dt_s1 - dt_e1
                        tarde = dt_s2 - dt_e2
                        df.loc[idx, 'total_trabalho'] = manha + tarde
                except:
                    df.loc[idx, 'total_trabalho'] = pd.Timedelta(0)
    
    if 'total_pausas' not in df.columns:
        df['total_pausas'] = pd.Timedelta(0)
    
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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Dashboard", "Visão Detalhada (Ponto)", "Análise de Intervalos", "Pontualidade Avançada", "📅 Tipos de Dia", "⚙️ Configurações"])
    edited_df = None

    with tab1:
        # Dashboard melhorado com KPIs (Fase 5)
        show_enhanced_dashboard_tab(df)
        
        # Mantém editor de dados na primeira aba também
        st.write("---")
        st.write("### ✏️ Editor Rápido")
        
        # Filtrar apenas dias com problemas para o editor rápido
        problematic_df = df.copy()
        
        # Filtrar dias úteis com problemas
        problematic_df = problematic_df[problematic_df['Data'].dt.weekday < 5]  # Apenas dias úteis
        
        # Remover tipos especiais
        if 'Tipo' in problematic_df.columns:
            special_types = ['folga', 'férias', 'feriado', 'ausência', 'baixa médica']
            for special_type in special_types:
                problematic_df = problematic_df[~problematic_df['Tipo'].str.contains(special_type, case=False, na=False)]
        
        # Filtrar apenas linhas com problemas reais
        has_problems = (
            (problematic_df.get('picagens_validas', True) == False) |
            (problematic_df.get('atraso_minutos', 0) > 0) |
            (problematic_df.get('tipo_problema', '').notna() & (problematic_df.get('tipo_problema', '') != ''))
        )
        problematic_df = problematic_df[has_problems]
        
        if problematic_df.empty:
            st.info("✅ Não há problemas para editar nos dias úteis!")
        else:
            st.write(f"📋 Mostrando **{len(problematic_df)}** dias com problemas:")
            
            # Define columns for summary view
            summary_cols = ['Data', 'Dia da Semana', 'Tipo', 'total_trabalho_calc', 'falta_td', 'extra_td', 'horas_efetivas_td', 'cumpriu_horario', 'aviso_picagens']
            display_df_summary = problematic_df[[col for col in summary_cols if col in problematic_df.columns]].copy()
            
            # Format timedelta columns for display
            for col in ['total_trabalho_calc', 'falta_td', 'extra_td', 'horas_efetivas_td']:
                if col in display_df_summary.columns:
                    display_df_summary[col] = display_df_summary[col].apply(format_timedelta_to_hhmm)

            # Configure the data editor (mostar apenas problemas)
            edited_df = st.data_editor(
                display_df_summary.head(10),  # Mostrar apenas primeiras 10 linhas com problemas
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
            height=350,
            key="data_editor" 
        )

    with tab2:
        # Editor detalhado com picagens editáveis
        st.write("### 📝 Editor Detalhado de Picagens")
        df = show_detailed_punch_editor(df)
    
    with tab3:
        # Análise de Intervalos (Fase 2)
        show_interval_analysis_tab(df)
    
    with tab4:
        # Análise de Pontualidade Avançada (Fase 3) + Editor Inteligente
        st.write("### 🔧 Editor Inteligente de Picagens")
        df = show_smart_punch_editor(df)
        
        st.write("---")
        show_punctuality_analysis_tab(df)
    
    with tab5:
        # Gestão de Tipos de Dia (Fase 5)
        df = show_day_type_management_tab(df)
    
    with tab6:
        # Configurações (Fase 4)
        show_config_tab(setor_selecionado)
    
    return edited_df

# Função principal
def main():
    setup_session_state()

    if uploaded_file is not None:
        if st.session_state.processed_data.empty:
            process_data(uploaded_file)
        
        df_to_analyze = st.session_state.get('edited_data', pd.DataFrame())

        if not df_to_analyze.empty:
            # Aplicar regras do setor selecionado (Fase 2)
            processor = CSVProcessor()
            df_to_analyze = processor.apply_sector_rules(df_to_analyze, setor_selecionado)
            st.session_state.edited_data = df_to_analyze
            
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
                    
                    # Reaplicar regras do setor após edições
                    df_to_analyze = processor.apply_sector_rules(df_to_analyze, setor_selecionado)
                    
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

def show_interval_analysis_tab(df):
    """Mostra análise inteligente de intervalos adaptada ao padrão de picagens."""
    st.write("### 🍽️ Análise de Intervalos")
    
    # Verificar se as colunas de análise de intervalos existem
    if 'detalhes_intervalos' not in df.columns:
        st.warning("⚠️ Análise de intervalos não disponível.")
        return
    
    # Detectar padrão predominante
    patterns = df['detalhes_intervalos'].str.extract(r'📋 Padrão: (\d+) picagens')
    pattern_counts = patterns[0].value_counts()
    
    if not pattern_counts.empty:
        main_pattern = pattern_counts.index[0]
        st.info(f"📊 **Padrão Detectado**: {main_pattern} picagens por dia")
        
        # Adaptar colunas baseado no padrão
        if main_pattern == '4':
            # Apenas almoço
            st.write("**🍽️ Análise: Apenas Almoço**")
            display_cols = ['Data', 'Tipo', 'duracao_almoco', 'conformidade_intervalos', 'alerta_intervalos']
            st.write("*Este padrão analisa apenas a duração do almoço (E1-S1-E2-S2)*")
            
        elif main_pattern == '6':
            # Lanche manhã + almoço
            st.write("**☕🍽️ Análise: Lanche Manhã + Almoço**") 
            display_cols = ['Data', 'Tipo', 'duracao_pausa_manha', 'duracao_almoco', 'conformidade_intervalos', 'alerta_intervalos']
            st.write("*Este padrão analisa lanche manhã e almoço (E1-S1-E2-S2-E3-S3)*")
            
        elif main_pattern == '8':
            # Todos os intervalos
            st.write("**☕🍽️☕ Análise: Lanche Manhã + Almoço + Lanche Tarde**")
            display_cols = ['Data', 'Tipo', 'duracao_pausa_manha', 'duracao_almoco', 'duracao_pausa_tarde', 'conformidade_intervalos', 'alerta_intervalos']
            st.write("*Este padrão analisa todos os intervalos (E1-S1-E2-S2-E3-S3-E4-S4)*")
        else:
            # Padrão misto ou irregular
            st.write("**🔀 Análise: Padrão Misto**")
            display_cols = ['Data', 'Tipo', 'duracao_almoco', 'conformidade_intervalos', 'alerta_intervalos']
    else:
        display_cols = ['Data', 'Tipo', 'duracao_almoco', 'alerta_intervalos']
    
    # Filtrar apenas colunas disponíveis
    available_cols = [col for col in display_cols if col in df.columns]
    
    if available_cols:
        # Formatar colunas de duração
        display_df = df[available_cols].copy()
        duration_cols = ['duracao_almoco', 'duracao_pausa_manha', 'duracao_pausa_tarde']
        
        for col in duration_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(format_timedelta_to_hhmm)
        
        st.dataframe(display_df, use_container_width=True)
        
        # Mostrar detalhes adicionais
        st.write("---")
        st.write("**📋 Detalhes por Dia:**")
        for idx, row in df.iterrows():
            if pd.notna(row.get('detalhes_intervalos')):
                data_str = row['Data'].strftime('%d/%m/%Y') if pd.notna(row['Data']) else 'N/A'
                with st.expander(f"📅 {data_str} - {row.get('Tipo', 'N/A')}"):
                    st.write(row['detalhes_intervalos'])

def show_punctuality_analysis_tab(df):
    """Mostra análise simples de pontualidade."""
    st.write("### 🎯 Análise de Pontualidade")
    
    # Tabela simples com dados de pontualidade
    punctuality_cols = ['Data', 'Tipo', 'tipo_problema', 'atraso_minutos', 'correcao_sugerida']
    available_cols = [col for col in punctuality_cols if col in df.columns]
    
    if available_cols:
        st.dataframe(df[available_cols], use_container_width=True)
    else:
        st.warning("⚠️ Dados de pontualidade não disponíveis.")
    

    
    # Tabela de problemas detectados
    problemas_df = df[df['requer_verificacao_manual'] == True]
    if not problemas_df.empty:
        st.write("#### 🔍 Problemas Detectados que Requerem Verificação")
        
        # Preparar dados para exibição
        display_problemas = problemas_df[['Data', 'Tipo', 'tipo_problema', 'picagens_sugeridas', 'correcao_sugerida']].copy()
        display_problemas['Data'] = display_problemas['Data'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(
            display_problemas,
            column_config={
                "Data": "Data",
                "Tipo": "Tipo de Dia",
                "tipo_problema": st.column_config.TextColumn(
                    "Problema Detectado",
                    help="Tipo de problema identificado automaticamente"
                ),
                "picagens_sugeridas": st.column_config.TextColumn(
                    "Sugestão",
                    help="Picagem sugerida para correção"
                ),
                "correcao_sugerida": st.column_config.TextColumn(
                    "Correção Recomendada",
                    help="Ação recomendada para corrigir o problema"
                )
            },
            use_container_width=True
        )
        
        # Botão para exportar lista de problemas
        if st.button("📋 Exportar Lista de Problemas"):
            csv_problemas = display_problemas.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_problemas,
                file_name=f"problemas_pontualidade_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # Análise de padrões
    st.write("#### 📈 Análise de Padrões")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Tipos de Problemas Mais Comuns:**")
        if not df[df['tipo_problema'] != ''].empty:
            problema_counts = df[df['tipo_problema'] != '']['tipo_problema'].value_counts()
            problema_data = pd.DataFrame({
                'Tipo de Problema': problema_counts.index,
                'Ocorrências': problema_counts.values
            })
            st.dataframe(problema_data, use_container_width=True)
        else:
            st.info("Nenhum problema detectado! 🎉")
    
    with col2:
        st.write("**Distribuição de Confiança das Sugestões:**")
        if 'confianca_sugestao' in df.columns:
            confianca_df = df[df['confianca_sugestao'] > 0]
            if not confianca_df.empty:
                # Criar categorias de confiança
                confianca_df_copy = confianca_df.copy()
                confianca_df_copy['categoria_confianca'] = pd.cut(
                    confianca_df_copy['confianca_sugestao'], 
                    bins=[0, 0.5, 0.8, 1.0], 
                    labels=['Baixa', 'Média', 'Alta']
                )
                
                confianca_counts = confianca_df_copy['categoria_confianca'].value_counts()
                st.dataframe(pd.DataFrame({
                    'Confiança': confianca_counts.index,
                    'Quantidade': confianca_counts.values
                }), use_container_width=True)
            else:
                st.info("Sem dados de confiança disponíveis")
    
    # Casos específicos para revisão manual
    if not problemas_df.empty:
        st.write("#### ⚠️ Casos Prioritários para Revisão")
        
        # Filtrar casos com alta confiança de sugestão
        casos_prioritarios = problemas_df[problemas_df['confianca_sugestao'] >= 0.7]
        
        if not casos_prioritarios.empty:
            st.write("**Casos com sugestões de alta confiança:**")
            for _, row in casos_prioritarios.head(5).iterrows():
                with st.expander(f"📅 {row['Data'].strftime('%d/%m/%Y')} - {row['tipo_problema']}"):
                    st.write(f"**Problema:** {row['tipo_problema']}")
                    st.write(f"**Sugestão:** {row['picagens_sugeridas']}")
                    st.write(f"**Correção:** {row['correcao_sugerida']}")
                    st.write(f"**Confiança:** {row['confianca_sugestao']:.1%}")
                    
                    # Aqui poderia ser adicionada uma interface para aplicar a correção
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"✅ Aplicar Sugestão", key=f"apply_{row.name}"):
                            st.success("Sugestão aplicada! (funcionalidade em desenvolvimento)")
                    with col_b:
                        if st.button(f"❌ Rejeitar", key=f"reject_{row.name}"):
                            st.info("Sugestão rejeitada")
        else:
            st.info("Não há casos prioritários no momento")

def show_enhanced_dashboard_tab(df: pd.DataFrame):
    """Mostra o dashboard melhorado com KPIs e visualizações."""
    try:
        from utils.kpi_calculator import KPICalculator
        from utils.day_type_manager import DayTypeManager
        
        kpi_calc = KPICalculator()
        day_manager = DayTypeManager()
        
        # Calcular KPIs principais
        kpis = kpi_calc.calculate_main_kpis(df)
        
        # Mostrar cards de KPIs
        kpi_calc.create_kpi_cards(kpis)
        
        # Linha de separação
        st.write("---")
        
        # Gráficos em colunas
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de tendências de pontualidade
            trends_fig = kpi_calc.create_punctuality_trends_chart(df)
            if trends_fig:
                st.plotly_chart(trends_fig, use_container_width=True)
            else:
                st.info("📊 Gráfico de tendências não disponível (dados insuficientes)")
        
        with col2:
            # Gráfico de breakdown de conformidade
            compliance_fig = kpi_calc.create_compliance_breakdown_chart(df)
            if compliance_fig:
                st.plotly_chart(compliance_fig, use_container_width=True)
            else:
                st.info("🎯 Gráfico de conformidade não disponível (dados insuficientes)")
        
        # Gráfico de horas semanais (largura completa)
        weekly_fig = kpi_calc.create_weekly_hours_chart(df)
        if weekly_fig:
            st.plotly_chart(weekly_fig, use_container_width=True)
        
        # Alertas ativos
        st.write("### 🚨 Alertas Prioritários")
        alerts = kpi_calc.generate_alerts_summary(df)
        
        if alerts:
            # Mostrar alertas em cards
            for alert in alerts[:5]:  # Máximo 5 alertas
                alert_color = {
                    'danger': '#dc3545',
                    'warning': '#ffc107', 
                    'info': '#17a2b8'
                }.get(alert['type'], '#6c757d')
                
                st.markdown(f"""
                <div style="
                    background: {alert_color}15;
                    border-left: 4px solid {alert_color};
                    padding: 0.8rem;
                    margin: 0.5rem 0;
                    border-radius: 4px;
                ">
                    <div style="display: flex; align-items: center;">
                        <span style="font-size: 1.2rem; margin-right: 0.5rem;">{alert['icon']}</span>
                        <strong>{alert['title']}</strong>
                        <span style="margin-left: auto; font-size: 0.9rem; color: #666;">
                            {alert['date']}
                        </span>
                    </div>
                    <div style="margin-top: 0.3rem; color: #666;">
                        {alert['message']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Nenhum alerta ativo no momento!")
            
    except ImportError as e:
        st.error(f"❌ Módulos não disponíveis: {e}")
        # Fallback para dashboard simples
        st.write("### 📊 Dados Básicos")
        st.dataframe(df.head(10))
    except Exception as e:
        st.error(f"❌ Erro no dashboard: {e}")
        # Fallback para dashboard simples
        st.write("### 📊 Dados Básicos")
        st.dataframe(df.head(10))

def show_day_type_management_tab(df: pd.DataFrame) -> pd.DataFrame:
    """Mostra a aba de gestão de tipos de dia."""
    try:
        from utils.day_type_manager import DayTypeManager
        
        day_manager = DayTypeManager()
        
        # Interface de gestão de tipos de dia
        updated_df = day_manager.create_streamlit_day_type_interface(df)
        
        return updated_df
        
    except ImportError:
        st.error("❌ Módulo de gestão de tipos de dia não disponível")
        return df
    except Exception as e:
        st.error(f"❌ Erro na gestão de tipos de dia: {e}")
        return df

def show_smart_punch_editor(df: pd.DataFrame) -> pd.DataFrame:
    """Editor inteligente para corrigir esquecimentos de picagens."""
    
    # Filtrar apenas dias com problemas que podem ser corrigidos
    problematic_days = df[
        (df.get('tipo_problema', '').notna()) & 
        (df.get('tipo_problema', '') != '') &
        (df.get('tipo_problema', '').str.contains('esquecimento|falta|missing', case=False, na=False)) &
        (~df.get('tipo_problema', '').str.contains('fim de semana|folga|férias', case=False, na=False))
    ].copy()
    
    if problematic_days.empty:
        st.info("✅ Não há esquecimentos de picagens para corrigir!")
        return df
    
    st.write(f"📋 Encontrados **{len(problematic_days)}** dias com possíveis esquecimentos:")
    
    # Mostrar cada problema com opção de correção
    for idx, row in problematic_days.head(5).iterrows():
        data_str = row['Data'].strftime('%d/%m/%Y')
        problema = row.get('tipo_problema', '')
        sugestao = row.get('correcao_sugerida', '')
        
        with st.expander(f"📅 {data_str} - {problema}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Problema:** {problema}")
                if sugestao:
                    st.write(f"**Sugestão:** {sugestao}")
                
                # Mostrar picagens atuais de forma mais clara
                current_punches = []
                punch_cols = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
                
                for punch_col in punch_cols:
                    if punch_col in row and pd.notna(row[punch_col]) and str(row[punch_col]) not in ['00:00', '0:00', '']:
                        current_punches.append(f"**{punch_col}**: {row[punch_col]}")
                
                if current_punches:
                    st.write("**Picagens atuais:**")
                    # Mostrar em formato de tabela simples
                    cols = st.columns(4)
                    for i, punch in enumerate(current_punches):
                        with cols[i % 4]:
                            st.write(punch)
                else:
                    st.write("**Picagens atuais:** ❌ Nenhuma picagem válida")
            
            with col2:
                if st.button(f"🔧 Corrigir", key=f"fix_{idx}"):
                    # Mostrar interface de correção
                    st.session_state[f'fixing_{idx}'] = True
                
                if st.session_state.get(f'fixing_{idx}', False):
                    st.write("**⚙️ Configurar nova picagem:**")
                    
                    # Sugerir hora baseada no problema
                    suggested_time = "08:00"  # Default
                    if "entrada" in problema.lower():
                        suggested_time = "08:00"
                    elif "saída" in problema.lower():
                        suggested_time = "17:00"
                    elif "almoço" in problema.lower():
                        suggested_time = "12:00"
                    
                    new_time = st.time_input(
                        "Hora da nova picagem:",
                        value=pd.to_datetime(suggested_time).time(),
                        key=f"time_{idx}",
                        help="Escolha a hora da picagem em falta"
                    )
                    
                    # Mostrar prévia do resultado
                    if st.checkbox("📋 Mostrar prévia", key=f"preview_{idx}"):
                        preview_result = preview_punch_correction(row, new_time, problema)
                        if preview_result:
                            st.write("**🔍 Resultado após correção:**")
                            st.json(preview_result)
                    
                    col_apply, col_cancel = st.columns(2)
                    with col_apply:
                        if st.button("✅ Aplicar Correção", key=f"apply_{idx}"):
                            # Aplicar correção
                            df = apply_punch_correction(df, idx, new_time, problema)
                            
                            # Reprocessar dados após correção
                            try:
                                from utils.csv_processor import CSVProcessor
                                processor = CSVProcessor()
                                setor = st.session_state.get('setor_selecionado', 'Produção')
                                df = processor.apply_sector_rules(df, setor)
                                st.session_state.edited_data = df
                                st.success(f"✅ Picagem corrigida e dados recalculados para {data_str}!")
                            except Exception as e:
                                st.warning(f"⚠️ Picagem corrigida mas erro no recálculo: {e}")
                            
                            st.session_state[f'fixing_{idx}'] = False
                            st.rerun()
                    
                    with col_cancel:
                        if st.button("❌ Cancelar", key=f"cancel_{idx}"):
                            st.session_state[f'fixing_{idx}'] = False
                            st.rerun()
    
    return df

def show_detailed_punch_editor(df: pd.DataFrame) -> pd.DataFrame:
    """Editor detalhado para editar tipos de dia e picagens."""
    
    st.write("📋 **Edite os tipos de dia e picagens diretamente na tabela abaixo:**")
    
    # Preparar colunas para edição
    detail_cols = ['Data', 'Dia da Semana', 'Tipo', 'E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
    edit_df = df[[col for col in detail_cols if col in df.columns]].copy()
    
    # Converter colunas de picagem para formato time compatível com Streamlit
    punch_cols = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
    for col in punch_cols:
        if col in edit_df.columns:
            # Converter strings de tempo para objetos time do pandas
            def convert_to_time(value):
                if pd.isna(value) or str(value) in ['00:00', '0:00', 'nan', 'None', '', 'NaT']:
                    return None
                try:
                    # Limpar e normalizar valor
                    value_str = str(value).strip()
                    if not value_str or value_str == 'nan':
                        return None
                    
                    # Tentar diferentes formatos
                    formats = ['%H:%M', '%H:%M:%S', '%I:%M %p']
                    for fmt in formats:
                        try:
                            time_obj = pd.to_datetime(value_str, format=fmt).time()
                            return time_obj
                        except:
                            continue
                    
                    # Se nenhum formato funcionou, tentar parsing automático
                    time_obj = pd.to_datetime(value_str).time()
                    return time_obj
                except:
                    return None
            
            edit_df[col] = edit_df[col].apply(convert_to_time)
    
    # Configuração das colunas editáveis
    column_config = {
        "Data": st.column_config.DateColumn(
            "Data",
            format="DD/MM/YYYY",
            disabled=True  # Data não editável
        ),
        "Dia da Semana": st.column_config.TextColumn(
            "Dia da Semana",
            disabled=True  # Dia da semana calculado automaticamente
        ),
        "Tipo": st.column_config.SelectboxColumn(
            "Tipo de Dia",
            help="Selecione o tipo de dia",
            options=['Normal', 'Falta', 'Falta parcial', 'Folga', 'Feriado', 'Férias', 'Baixa médica', 'Compensação', 'Formação'],
            required=True,
        )
    }
    
    # Configurar colunas de picagem como editáveis
    for col in punch_cols:
        if col in edit_df.columns:
            column_config[col] = st.column_config.TimeColumn(
                col,
                help=f"Edite a hora da picagem {col} (formato HH:MM)",
                format="HH:mm",
                min_value=pd.to_datetime("00:00", format='%H:%M').time(),
                max_value=pd.to_datetime("23:59", format='%H:%M').time()
            )
    
    # Editor de dados
    edited_detail_df = st.data_editor(
        edit_df,
        column_config=column_config,
        use_container_width=True,
        height=400,
        key="detailed_editor"
    )
    
    # Aplicar mudanças de volta ao DataFrame principal
    if not edited_detail_df.equals(edit_df):
        st.info("✏️ Alterações detectadas! Aplicando mudanças...")
        
        # Atualizar DataFrame principal com as edições
        for idx, row in edited_detail_df.iterrows():
            if idx in df.index:
                # Atualizar tipo
                if 'Tipo' in row:
                    df.loc[idx, 'Tipo'] = row['Tipo']
                
                # Atualizar picagens
                for col in punch_cols:
                    if col in row and col in df.columns:
                        # Converter volta para formato string HH:MM
                        value = row[col]
                        if pd.isna(value) or value is None:
                            df.loc[idx, col] = '00:00'
                        else:
                            # Se é um objeto time, converter para string
                            if hasattr(value, 'strftime'):
                                df.loc[idx, col] = value.strftime('%H:%M')
                            else:
                                df.loc[idx, col] = str(value) if str(value) != 'nan' else '00:00'
        
        # Reprocessar dados após edições
        try:
            from utils.csv_processor import CSVProcessor
            processor = CSVProcessor()
            
            # Aplicar regras do setor após edições
            setor = st.session_state.get('setor_selecionado', 'Produção')
            df = processor.apply_sector_rules(df, setor)
            
            st.success("✅ Alterações aplicadas e dados reprocessados!")
            st.rerun()
            
        except Exception as e:
            st.warning(f"⚠️ Erro ao reprocessar dados: {e}")
    
    return df

def apply_punch_correction(df: pd.DataFrame, row_idx: int, new_time, problem_type: str) -> pd.DataFrame:
    """Aplica correção de picagem movendo as picagens existentes de forma inteligente."""
    
    time_str = new_time.strftime('%H:%M')
    punch_cols = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
    
    # Obter picagens atuais não-vazias com seus tempos
    current_punches = []
    for i, punch_col in enumerate(punch_cols):
        if punch_col in df.columns and pd.notna(df.iloc[row_idx][punch_col]):
            val = str(df.iloc[row_idx][punch_col])
            if val not in ['00:00', '0:00', '', 'nan']:
                try:
                    # Converter para minutos para comparação
                    time_parts = val.split(':')
                    minutes = int(time_parts[0]) * 60 + int(time_parts[1])
                    current_punches.append({
                        'col': punch_col,
                        'time': val,
                        'minutes': minutes,
                        'index': i,
                        'type': 'E' if punch_col.startswith('E') else 'S'
                    })
                except:
                    pass
    
    # Converter nova picagem para minutos
    new_time_parts = time_str.split(':')
    new_minutes = int(new_time_parts[0]) * 60 + int(new_time_parts[1])
    
    # Determinar tipo da nova picagem e onde inserir
    new_punch_type = determine_punch_type(problem_type, current_punches, new_minutes)
    
    # Criar lista final de picagens com a nova inserida
    final_punches = insert_punch_intelligently(current_punches, time_str, new_minutes, new_punch_type)
    
    # Limpar todas as picagens primeiro
    for punch_col in punch_cols:
        if punch_col in df.columns:
            df.loc[row_idx, punch_col] = '00:00'
    
    # Aplicar picagens reorganizadas
    for i, punch in enumerate(final_punches[:8]):  # Máximo 8 picagens
        if i < len(punch_cols):
            df.loc[row_idx, punch_cols[i]] = punch['time']
    
    return df

def determine_punch_type(problem_type: str, current_punches: list, new_minutes: int) -> str:
    """Determina o tipo da nova picagem (E ou S) baseado no problema e contexto."""
    
    problem_lower = problem_type.lower()
    
    # Casos explícitos
    if "entrada" in problem_lower or "chegada" in problem_lower:
        return 'E'
    elif "saída" in problem_lower or "saida" in problem_lower:
        return 'S'
    elif "almoço" in problem_lower or "almoco" in problem_lower:
        # Para almoço, determinar se é saída ou entrada baseado no horário
        if new_minutes < 12 * 60:  # Antes do meio-dia = saída para almoço
            return 'S'
        else:  # Depois do meio-dia = entrada do almoço
            return 'E'
    
    # Lógica automática baseada no padrão atual
    if not current_punches:
        return 'E'  # Primeira picagem é sempre entrada
    
    # Contar entradas e saídas
    entries = sum(1 for p in current_punches if p['type'] == 'E')
    exits = sum(1 for p in current_punches if p['type'] == 'S')
    
    # Padrão normal: E1, S1, E2, S2, E3, S3, E4, S4
    if entries > exits:
        return 'S'  # Falta uma saída
    else:
        return 'E'  # Falta uma entrada

def insert_punch_intelligently(current_punches: list, new_time: str, new_minutes: int, new_type: str) -> list:
    """Insere a nova picagem na posição cronológica correta e reorganiza as outras."""
    
    # Adicionar nova picagem à lista
    new_punch = {
        'time': new_time,
        'minutes': new_minutes,
        'type': new_type,
        'is_new': True
    }
    
    all_punches = current_punches + [new_punch]
    
    # Ordenar cronologicamente
    all_punches.sort(key=lambda x: x['minutes'])
    
    # Reorganizar para manter padrão E-S-E-S
    reorganized = []
    entries = []
    exits = []
    
    # Separar entradas e saídas mantendo ordem cronológica
    for punch in all_punches:
        if punch['type'] == 'E':
            entries.append(punch)
        else:
            exits.append(punch)
    
    # Reconstruir padrão E-S-E-S
    max_pairs = min(len(entries), len(exits))
    
    # Adicionar pares E-S
    for i in range(max_pairs):
        reorganized.append(entries[i])
        reorganized.append(exits[i])
    
    # Adicionar entradas/saídas restantes
    if len(entries) > max_pairs:
        reorganized.extend(entries[max_pairs:])
    if len(exits) > max_pairs:
        reorganized.extend(exits[max_pairs:])
    
    return reorganized

def preview_punch_correction(row, new_time, problem_type: str) -> dict:
    """Mostra uma prévia de como ficará após a correção."""
    
    time_str = new_time.strftime('%H:%M')
    punch_cols = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
    
    # Obter picagens atuais
    current_punches = []
    for i, punch_col in enumerate(punch_cols):
        if punch_col in row and pd.notna(row[punch_col]):
            val = str(row[punch_col])
            if val not in ['00:00', '0:00', '', 'nan']:
                try:
                    time_parts = val.split(':')
                    minutes = int(time_parts[0]) * 60 + int(time_parts[1])
                    current_punches.append({
                        'col': punch_col,
                        'time': val,
                        'minutes': minutes,
                        'index': i,
                        'type': 'E' if punch_col.startswith('E') else 'S'
                    })
                except:
                    pass
    
    # Simular a correção
    new_time_parts = time_str.split(':')
    new_minutes = int(new_time_parts[0]) * 60 + int(new_time_parts[1])
    new_punch_type = determine_punch_type(problem_type, current_punches, new_minutes)
    final_punches = insert_punch_intelligently(current_punches, time_str, new_minutes, new_punch_type)
    
    # Criar resultado para exibição
    result = {}
    
    # Mostrar antes
    antes = {}
    for punch in current_punches:
        antes[punch['col']] = punch['time']
    result['Antes'] = antes if antes else {"Status": "Nenhuma picagem"}
    
    # Mostrar depois
    depois = {}
    for i, punch in enumerate(final_punches[:8]):
        if i < len(punch_cols):
            depois[punch_cols[i]] = punch['time']
            if punch.get('is_new'):
                depois[punch_cols[i]] += " ⭐ (NOVA)"
    
    result['Depois'] = depois
    result['Nova picagem'] = f"{new_punch_type}: {time_str}"
    result['Tipo detectado'] = f"{'Entrada' if new_punch_type == 'E' else 'Saída'}"
    
    return result

def show_config_tab(sector: str):
    """Mostra a aba de configurações."""
    st.write("### ⚙️ Configuração de Horários e Regras")
    
    try:
        from utils.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Interface de configuração
        st.write("#### 🏢 Configurações por Setor")
        st.info("Configure horários de trabalho, tolerâncias e regras de detecção para cada setor.")
        
        # Mostrar interface para o setor selecionado
        updated_config = config_manager.create_streamlit_config_interface(sector)
        
        # Mostrar configuração atual
        st.write("#### 📋 Configuração Atual")
        config_df = pd.DataFrame([updated_config]).T
        config_df.columns = ['Valor']
        st.dataframe(config_df, use_container_width=True)
        
        # Explicação das tolerâncias
        st.write("#### ❓ Ajuda - Configurações")
        
        with st.expander("🕐 Tolerâncias - Como Funcionam"):
            st.write("""
            **Tolerância de Entrada:** Atraso aceitável sem gerar alerta.
            
            **Tolerância de Saída:** Antecipação aceitável na saída.
            
            **Tolerância de Esquecimento:** Valor crítico para distinguir entre:
            - Atraso normal (pessoa chegou tarde)
            - Esquecimento de picagem (pessoa esqueceu-se de picar)
            
            **Exemplo:** Se tolerância de esquecimento = 30 min
            - Entrada às 09:00 (atraso 30 min) = Atraso normal
            - Entrada às 10:00 (atraso 60 min) = Possível esquecimento
            """)
        
        with st.expander("📊 Detecção Inteligente"):
            st.write("""
            O sistema analisa automaticamente:
            
            1. **Padrão de picagens** vs horário configurado
            2. **Tolerâncias específicas** do setor
            3. **Contexto temporal** (gaps entre picagens)
            
            **Cenários detectados:**
            - ✅ Trabalho normal
            - ⚠️ Atraso tolerável 
            - 🔍 Possível esquecimento de entrada/saída
            - 📝 Padrão irregular (requer verificação)
            """)
        
        # Botão para resetar configurações
        st.write("#### 🔄 Gestão de Configurações")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Resetar para Padrão", help="Restaura configurações padrão do setor"):
                config_manager.current_config['horarios_setor'][sector] = config_manager.default_config['horarios_setor'][sector].copy()
                if config_manager.save_config():
                    st.success("✅ Configurações resetadas!")
                    st.rerun()
        
        with col2:
            if st.button("📤 Exportar Configurações"):
                config_json = json.dumps(config_manager.current_config, indent=2, ensure_ascii=False)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=config_json,
                    file_name=f"config_horarios_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
        
    except ImportError:
        st.error("❌ Módulo de configurações não disponível")
    except Exception as e:
        st.error(f"❌ Erro ao carregar configurações: {e}")

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
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Download Excel", key="excel_download"):
            try:
                from utils.report_generator import ReportGenerator
                report_gen = ReportGenerator()
                
                # Usar dados mais recentes da sessão se disponível
                data_to_export = st.session_state.get('edited_data', df)
                excel_buffer = report_gen.generate_excel_report(data_to_export, setor)
                
                st.download_button(
                    label="⬇️ Baixar Relatório Excel",
                    data=excel_buffer,
                    file_name=f"relatorio_horas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_download_btn"
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar Excel: {e}")
    
    with col2:
        if st.button("📄 Download CSV", key="csv_download"):
            try:
                from utils.report_generator import ReportGenerator
                report_gen = ReportGenerator()
                
                # Usar dados mais recentes da sessão se disponível
                data_to_export = st.session_state.get('edited_data', df)
                csv_buffer = report_gen.generate_csv_report(data_to_export)
                
                st.download_button(
                    label="⬇️ Baixar Relatório CSV",
                    data=csv_buffer,
                    file_name=f"relatorio_horas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    key="csv_download_btn"
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar CSV: {e}")

if __name__ == "__main__":
    main() 
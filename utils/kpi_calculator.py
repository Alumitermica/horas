import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st

class KPICalculator:
    """
    Classe responsável pelo cálculo e visualização de KPIs:
    - Métricas principais (horas, pontualidade, conformidade)
    - Gráficos e dashboards visuais
    - Alertas e tendências
    - Comparações e benchmarks
    """
    
    def __init__(self):
        """Inicializa o calculador de KPIs."""
        pass
    
    def calculate_main_kpis(self, df: pd.DataFrame) -> Dict:
        """
        Calcula os KPIs principais.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Dict com todos os KPIs calculados
        """
        if df.empty:
            return self._get_empty_kpis()
        
        # Filtrar apenas dias com dados válidos
        valid_days = df[df['picagens_validas'] == True]
        
        # KPIs principais
        kpis = {
            'total_days': len(df),
            'work_days': len(valid_days),
            'absence_days': len(df) - len(valid_days),
            'total_hours': self._calculate_total_hours(valid_days),
            'avg_daily_hours': 0.0,
            'punctuality_rate': self._calculate_punctuality_rate(valid_days),
            'avg_delay_minutes': self._calculate_avg_delay(valid_days),
            'overtime_hours': self._calculate_overtime_hours(valid_days),
            'compliance_rate': self._calculate_compliance_rate(df),
            'active_alerts': self._count_active_alerts(df),
            'period_start': None,
            'period_end': None,
            'longest_delay': 0,
            'perfect_days': 0,
            'problematic_days': 0
        }
        
        # Calcular média diária
        if kpis['work_days'] > 0:
            kpis['avg_daily_hours'] = kpis['total_hours'] / kpis['work_days']
        
        # Período analisado
        if 'Data' in df.columns and not df.empty:
            dates = pd.to_datetime(df['Data']).dropna()
            if not dates.empty:
                kpis['period_start'] = dates.min().date()
                kpis['period_end'] = dates.max().date()
        
        # Análise de pontualidade detalhada
        if 'atraso_minutos' in df.columns:
            delays = df['atraso_minutos'].fillna(0)
            kpis['longest_delay'] = delays.max()
            kpis['perfect_days'] = len(df[delays == 0])
        
        # Dias problemáticos (com alertas)
        if 'tipo_problema' in df.columns:
            kpis['problematic_days'] = len(df[df['tipo_problema'].notna() & (df['tipo_problema'] != '')])
        
        return kpis
    
    def _get_empty_kpis(self) -> Dict:
        """Retorna KPIs vazios para DataFrames sem dados."""
        return {
            'total_days': 0,
            'work_days': 0,
            'absence_days': 0,
            'total_hours': 0.0,
            'avg_daily_hours': 0.0,
            'punctuality_rate': 0.0,
            'avg_delay_minutes': 0.0,
            'overtime_hours': 0.0,
            'compliance_rate': 0.0,
            'active_alerts': 0,
            'period_start': None,
            'period_end': None,
            'longest_delay': 0,
            'perfect_days': 0,
            'problematic_days': 0
        }
    
    def _calculate_total_hours(self, df: pd.DataFrame) -> float:
        """Calcula total de horas trabalhadas."""
        # Procurar por diferentes possíveis nomes de colunas
        hour_columns = ['total_trabalho', 'Efect', 'horas_efetivas_num', 'horas_trabalhadas', 'total_trabalho_calc', 'horas_efetivas_td']
        
        for col in hour_columns:
            if col in df.columns:
                # Se for timedelta, converter para horas
                if df[col].dtype == 'timedelta64[ns]':
                    return df[col].fillna(pd.Timedelta(0)).dt.total_seconds().sum() / 3600
                elif col in ['Efect', 'total_trabalho']:
                    # Colunas em formato HH:MM como string ou timedelta
                    if df[col].dtype == 'timedelta64[ns]':
                        return df[col].fillna(pd.Timedelta(0)).dt.total_seconds().sum() / 3600
                    else:
                        total_seconds = 0
                        for value in df[col].fillna('00:00'):
                            if isinstance(value, str) and ':' in value:
                                try:
                                    parts = value.split(':')
                                    if len(parts) == 2:
                                        hours = int(parts[0])
                                        minutes = int(parts[1])
                                        total_seconds += hours * 3600 + minutes * 60
                                except:
                                    pass
                        return total_seconds / 3600
                else:
                    return df[col].fillna(0).sum()
        return 0.0
    
    def _calculate_punctuality_rate(self, df: pd.DataFrame) -> float:
        """Calcula taxa de pontualidade."""
        if df.empty:
            return 0.0
        
        if 'atraso_minutos' in df.columns:
            punctual_days = len(df[df['atraso_minutos'].fillna(0) <= 10])  # Até 10min = pontual
            return (punctual_days / len(df)) * 100
        
        return 100.0  # Se não há dados de atraso, assume pontual
    
    def _calculate_avg_delay(self, df: pd.DataFrame) -> float:
        """Calcula atraso médio em minutos."""
        if 'atraso_minutos' in df.columns:
            delays = df['atraso_minutos'].fillna(0)
            return delays[delays > 0].mean() if len(delays[delays > 0]) > 0 else 0.0
        return 0.0
    
    def _calculate_overtime_hours(self, df: pd.DataFrame) -> float:
        """Calcula total de horas extra."""
        # Procurar coluna de horas extras específica primeiro
        if 'Extra' in df.columns:
            # Coluna Extra está em formato HH:MM como string
            total_seconds = 0
            for value in df['Extra'].fillna('00:00'):
                if isinstance(value, str) and ':' in value:
                    try:
                        parts = value.split(':')
                        if len(parts) == 2:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            total_seconds += hours * 3600 + minutes * 60
                    except:
                        pass
            return total_seconds / 3600
        
        elif 'extra_td' in df.columns:
            if df['extra_td'].dtype == 'timedelta64[ns]':
                return df['extra_td'].fillna(pd.Timedelta(0)).dt.total_seconds().sum() / 3600
            else:
                return df['extra_td'].fillna(0).sum()
        
        # Fallback: calcular baseado nas horas efetivas
        hour_columns = ['total_trabalho', 'Efect', 'horas_efetivas_num', 'horas_trabalhadas']
        for col in hour_columns:
            if col in df.columns:
                if df[col].dtype == 'timedelta64[ns]':
                    hours = df[col].fillna(pd.Timedelta(0)).dt.total_seconds() / 3600
                elif col in ['Efect', 'total_trabalho']:
                    # Processar formato HH:MM ou timedelta
                    if df[col].dtype == 'timedelta64[ns]':
                        hours = df[col].fillna(pd.Timedelta(0)).dt.total_seconds() / 3600
                    else:
                        hours = []
                        for value in df[col].fillna('00:00'):
                            if isinstance(value, str) and ':' in value:
                                try:
                                    parts = value.split(':')
                                    if len(parts) == 2:
                                        h = int(parts[0]) + int(parts[1]) / 60
                                        hours.append(h)
                                except:
                                    hours.append(0)
                            else:
                                hours.append(0)
                        hours = pd.Series(hours)
                else:
                    hours = df[col].fillna(0)
                # Assumir 8h como padrão
                overtime = hours - 8.0
                return overtime[overtime > 0].sum()
        return 0.0
    
    def _calculate_compliance_rate(self, df: pd.DataFrame) -> float:
        """Calcula taxa de conformidade geral."""
        if df.empty:
            return 0.0
        
        compliant_days = 0
        total_days = len(df)
        
        for _, row in df.iterrows():
            # Verificar múltiplos fatores de conformidade
            issues = 0
            
            # Picagens válidas
            if not row.get('picagens_validas', True):
                issues += 1
            
            # Atrasos significativos (>15min)
            if row.get('atraso_minutos', 0) > 15:
                issues += 1
            
            # Problemas de pontualidade
            if row.get('tipo_problema', '') not in ['', None]:
                issues += 1
            
            # Se não tem problemas, é conforme
            if issues == 0:
                compliant_days += 1
        
        return (compliant_days / total_days) * 100 if total_days > 0 else 0.0
    
    def _count_active_alerts(self, df: pd.DataFrame) -> int:
        """Conta alertas ativos."""
        alerts = 0
        
        # Alertas de picagens
        if 'aviso_picagens' in df.columns:
            alerts += len(df[df['aviso_picagens'].notna() & (df['aviso_picagens'] != '')])
        
        # Alertas de intervalos
        if 'alertas_intervalos' in df.columns:
            alerts += len(df[df['alertas_intervalos'].notna() & (df['alertas_intervalos'] != '')])
        
        # Problemas de pontualidade
        if 'tipo_problema' in df.columns:
            alerts += len(df[df['tipo_problema'].notna() & (df['tipo_problema'] != '')])
        
        return alerts
    
    def create_kpi_cards(self, kpis: Dict) -> None:
        """
        Cria cards visuais com KPIs principais.
        
        Args:
            kpis: Dicionário com KPIs calculados
        """
        st.write("### 📊 KPIs Principais")
        
        # Primeira linha de cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            self._create_kpi_card(
                title="Horas Trabalhadas",
                value=f"{kpis['total_hours']:.1f}h",
                subtitle=f"Média: {kpis['avg_daily_hours']:.1f}h/dia",
                icon="⏰",
                color="#28a745"
            )
        
        with col2:
            self._create_kpi_card(
                title="Pontualidade",
                value=f"{kpis['punctuality_rate']:.1f}%",
                subtitle=f"Atraso médio: {kpis['avg_delay_minutes']:.0f}min",
                icon="🎯",
                color="#17a2b8" if kpis['punctuality_rate'] >= 90 else "#ffc107"
            )
        
        with col3:
            self._create_kpi_card(
                title="Conformidade",
                value=f"{kpis['compliance_rate']:.1f}%",
                subtitle=f"{kpis['perfect_days']} dias perfeitos",
                icon="✅",
                color="#28a745" if kpis['compliance_rate'] >= 95 else "#dc3545"
            )
        
        with col4:
            self._create_kpi_card(
                title="Alertas Ativos",
                value=str(kpis['active_alerts']),
                subtitle=f"{kpis['problematic_days']} dias problemáticos",
                icon="⚠️",
                color="#dc3545" if kpis['active_alerts'] > 0 else "#28a745"
            )
        
        # Segunda linha de cards
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            self._create_kpi_card(
                title="Dias de Trabalho",
                value=str(kpis['work_days']),
                subtitle=f"Total: {kpis['total_days']} dias",
                icon="📅",
                color="#6c757d"
            )
        
        with col6:
            self._create_kpi_card(
                title="Horas Extra",
                value=f"{kpis['overtime_hours']:.1f}h",
                subtitle="Acima das 8h diárias",
                icon="⏰",
                color="#fd7e14" if kpis['overtime_hours'] > 10 else "#28a745"
            )
        
        with col7:
            self._create_kpi_card(
                title="Maior Atraso",
                value=f"{kpis['longest_delay']:.0f}min",
                subtitle="No período analisado",
                icon="⌛",
                color="#dc3545" if kpis['longest_delay'] > 30 else "#ffc107"
            )
        
        with col8:
            period_text = "N/A"
            if kpis['period_start'] and kpis['period_end']:
                days = (kpis['period_end'] - kpis['period_start']).days + 1
                period_text = f"{days} dias"
            
            self._create_kpi_card(
                title="Período",
                value=period_text,
                subtitle=f"{kpis['period_start']} a {kpis['period_end']}" if kpis['period_start'] else "Sem dados",
                icon="📊",
                color="#6610f2"
            )
    
    def _create_kpi_card(self, title: str, value: str, subtitle: str, icon: str, color: str) -> None:
        """Cria um card individual de KPI."""
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {color}15, {color}25);
            border-left: 4px solid {color};
            padding: 1rem;
            border-radius: 8px;
            margin: 0.5rem 0;
            text-align: center;
        ">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-size: 1.2rem; font-weight: bold; color: {color};">{value}</div>
            <div style="font-size: 0.9rem; font-weight: bold; margin: 0.2rem 0;">{title}</div>
            <div style="font-size: 0.8rem; color: #666;">{subtitle}</div>
        </div>
        """, unsafe_allow_html=True)
    
    def create_punctuality_trends_chart(self, df: pd.DataFrame) -> Optional[go.Figure]:
        """
        Cria gráfico de tendências de pontualidade.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Figura Plotly ou None se não há dados
        """
        if df.empty or 'Data' not in df.columns:
            return None
        
        # Preparar dados
        df_chart = df.copy()
        df_chart['Data'] = pd.to_datetime(df_chart['Data'])
        
        if 'atraso_minutos' not in df_chart.columns:
            df_chart['atraso_minutos'] = 0
        
        # Criar figura simples para atrasos diários
        fig = go.Figure()
        
        # Gráfico de atrasos diários
        colors = ['#dc3545' if delay > 15 else '#ffc107' if delay > 0 else '#28a745' 
                 for delay in df_chart['atraso_minutos'].fillna(0)]
        
        fig.add_trace(
            go.Scatter(
                x=df_chart['Data'],
                y=df_chart['atraso_minutos'].fillna(0),
                mode='markers+lines',
                name='Atraso (min)',
                marker=dict(
                    color=colors,
                    size=8,
                    line=dict(width=1, color='white')
                ),
                line=dict(width=2, color='#6c757d'),
                hovertemplate='<b>%{x}</b><br>Atraso: %{y} min<extra></extra>'
            )
        )
        
        # Linha de referência (15min)
        fig.add_hline(y=15, line_dash="dash", line_color="red", 
                     annotation_text="Limite tolerância")
        
        # Layout
        fig.update_layout(
            title="📈 Atrasos Diários",
            showlegend=True,
            height=400,
            template="plotly_white",
            xaxis_title="Data",
            yaxis_title="Atraso (minutos)"
        )
        
        return fig
    
    def create_compliance_breakdown_chart(self, df: pd.DataFrame) -> Optional[go.Figure]:
        """
        Cria gráfico de breakdown de conformidade.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Figura Plotly ou None se não há dados
        """
        if df.empty:
            return None
        
        # Categorizar dias por tipo de conformidade
        categories = {
            'Perfeito': 0,
            'Pequenos Atrasos': 0,
            'Atrasos Moderados': 0,
            'Atrasos Graves': 0,
            'Problemas de Picagem': 0,
            'Sem Dados': 0
        }
        
        colors = {
            'Perfeito': '#28a745',
            'Pequenos Atrasos': '#20c997',
            'Atrasos Moderados': '#ffc107',
            'Atrasos Graves': '#fd7e14',
            'Problemas de Picagem': '#dc3545',
            'Sem Dados': '#6c757d'
        }
        
        for _, row in df.iterrows():
            # Verificar picagens válidas
            if not row.get('picagens_validas', True):
                categories['Problemas de Picagem'] += 1
            
            # Verificar se tem dados de atraso
            elif 'atraso_minutos' not in row or pd.isna(row.get('atraso_minutos')):
                categories['Sem Dados'] += 1
            
            else:
                atraso = row.get('atraso_minutos', 0)
                
                if atraso == 0:
                    categories['Perfeito'] += 1
                elif atraso <= 10:
                    categories['Pequenos Atrasos'] += 1
                elif atraso <= 30:
                    categories['Atrasos Moderados'] += 1
                else:
                    categories['Atrasos Graves'] += 1
        
        # Filtrar categorias com dados
        active_categories = {k: v for k, v in categories.items() if v > 0}
        
        if not active_categories:
            return None
        
        # Criar gráfico de pizza
        fig = go.Figure(data=[
            go.Pie(
                labels=list(active_categories.keys()),
                values=list(active_categories.values()),
                hole=0.4,
                marker=dict(
                    colors=[colors[cat] for cat in active_categories.keys()],
                    line=dict(color='white', width=2)
                ),
                textinfo='label+percent+value',
                textfont=dict(size=12),
                hovertemplate='<b>%{label}</b><br>%{value} dias (%{percent})<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title="🎯 Breakdown de Conformidade",
            annotations=[dict(text='Conformidade<br>Geral', x=0.5, y=0.5, font_size=16, showarrow=False)],
            height=400,
            template="plotly_white"
        )
        
        return fig
    
    def create_weekly_hours_chart(self, df: pd.DataFrame) -> Optional[go.Figure]:
        """
        Cria gráfico de horas trabalhadas por semana.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Figura Plotly ou None se não há dados
        """
        if df.empty or 'Data' not in df.columns:
            return None
        
        # Encontrar coluna de horas
        hour_col = None
        for col in ['total_trabalho', 'Efect', 'horas_efetivas_num', 'horas_trabalhadas', 'total_trabalho_calc']:
            if col in df.columns:
                hour_col = col
                break
        
        if hour_col is None:
            return None
        
        # Preparar dados
        df_chart = df.copy()
        df_chart['Data'] = pd.to_datetime(df_chart['Data'])
        df_chart['Semana'] = df_chart['Data'].dt.to_period('W').dt.start_time
        
        # Preparar dados para agregação
        if df_chart[hour_col].dtype == 'timedelta64[ns]':
            df_chart['horas_num'] = df_chart[hour_col].dt.total_seconds() / 3600
        elif hour_col in ['Efect', 'total_trabalho']:
            # Processar formato HH:MM ou timedelta
            if df_chart[hour_col].dtype == 'timedelta64[ns]':
                df_chart['horas_num'] = df_chart[hour_col].dt.total_seconds() / 3600
            else:
                hours = []
                for value in df_chart[hour_col].fillna('00:00'):
                    if isinstance(value, str) and ':' in value:
                        try:
                            parts = value.split(':')
                            if len(parts) == 2:
                                h = int(parts[0]) + int(parts[1]) / 60
                                hours.append(h)
                        except:
                            hours.append(0)
                    else:
                        hours.append(0)
                df_chart['horas_num'] = hours
        else:
            df_chart['horas_num'] = df_chart[hour_col].fillna(0)
        
        # Filtrar apenas dias de trabalho (não fins de semana/férias)
        df_work_days = df_chart.copy()
        
        # Aplicar filtros para dias úteis
        if 'Tipo' in df_work_days.columns:
            # Remover tipos especiais
            special_types = ['folga', 'férias', 'feriado', 'ausência', 'baixa médica']
            for special_type in special_types:
                df_work_days = df_work_days[~df_work_days['Tipo'].str.contains(special_type, case=False, na=False)]
        
        # Remover fins de semana
        df_work_days = df_work_days[df_work_days['Data'].dt.weekday < 5]  # Segunda=0 a Sexta=4
        
        # Agrupar por semana
        weekly_data = df_work_days.groupby('Semana').agg({
            'horas_num': ['sum', 'mean', 'count']
        }).reset_index()
        
        weekly_data.columns = ['Semana', 'Total_Horas', 'Media_Horas', 'Dias_Trabalhados']
        
        # Criar gráfico
        fig = make_subplots(
            rows=1, cols=1,
            specs=[[{"secondary_y": True}]]
        )
        
        # Barras: Total de horas
        fig.add_trace(
            go.Bar(
                x=weekly_data['Semana'],
                y=weekly_data['Total_Horas'],
                name='Total Horas',
                marker_color='#17a2b8',
                opacity=0.7,
                hovertemplate='<b>Semana de %{x}</b><br>Total: %{y:.1f}h<extra></extra>'
            ),
            row=1, col=1, secondary_y=False
        )
        
        # Linha: Média diária
        fig.add_trace(
            go.Scatter(
                x=weekly_data['Semana'],
                y=weekly_data['Media_Horas'],
                mode='markers+lines',
                name='Média Diária',
                marker=dict(color='#dc3545', size=8),
                line=dict(width=3, color='#dc3545'),
                hovertemplate='<b>Semana de %{x}</b><br>Média: %{y:.1f}h/dia<extra></extra>'
            ),
            row=1, col=1, secondary_y=True
        )
        
        # Linha de referência (8h/dia)
        fig.add_hline(y=8, line_dash="dash", line_color="green", 
                     annotation_text="Meta: 8h/dia", row=1, col=1, secondary_y=True)
        
        # Layout
        fig.update_layout(
            title="📊 Horas Trabalhadas por Semana",
            height=400,
            template="plotly_white"
        )
        
        fig.update_xaxes(title_text="Semana", row=1, col=1)
        fig.update_yaxes(title_text="Total de Horas", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Média Diária (h)", row=1, col=1, secondary_y=True)
        
        return fig
    
    def generate_alerts_summary(self, df: pd.DataFrame) -> List[Dict]:
        """
        Gera resumo de alertas prioritários.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Lista de dicionários com alertas
        """
        alerts = []
        
        if df.empty:
            return alerts
        
        # Filtrar apenas dias úteis para alertas
        df_work = df.copy()
        
        # Remover fins de semana
        if 'Data' in df_work.columns:
            df_work = df_work[df_work['Data'].dt.weekday < 5]
        
        # Remover tipos especiais
        if 'Tipo' in df_work.columns:
            special_types = ['folga', 'férias', 'feriado', 'ausência', 'baixa médica']
            for special_type in special_types:
                df_work = df_work[~df_work['Tipo'].str.contains(special_type, case=False, na=False)]
        
        # Alertas de atrasos graves (>30min) apenas em dias úteis
        if 'atraso_minutos' in df_work.columns:
            grave_delays = df_work[df_work['atraso_minutos'].fillna(0) > 30]
            for _, row in grave_delays.iterrows():
                alerts.append({
                    'type': 'danger',
                    'icon': '🚨',
                    'title': 'Atraso Grave',
                    'message': f"Atraso de {row['atraso_minutos']:.0f} minutos",
                    'date': row.get('Data', 'N/A'),
                    'priority': 'high'
                })
        
        # Alertas de picagens inválidas apenas em dias úteis
        invalid_punches = df_work[df_work.get('picagens_validas', True) == False]
        for _, row in invalid_punches.iterrows():
            # Verificar se é realmente um problema (não falta justificada)
            if row.get('Tipo', '').lower() not in ['falta', 'ausência']:
                alerts.append({
                    'type': 'warning',
                    'icon': '⚠️',
                    'title': 'Picagens Inválidas',
                    'message': row.get('aviso_picagens', 'Problema nas picagens'),
                    'date': row.get('Data', 'N/A'),
                    'priority': 'medium'
                })
        
        # Alertas de problemas de pontualidade apenas em dias úteis
        if 'tipo_problema' in df_work.columns:
            punctuality_issues = df_work[
                df_work['tipo_problema'].notna() & 
                (df_work['tipo_problema'] != '') &
                (~df_work['tipo_problema'].str.contains('fim de semana|folga|férias', case=False, na=False))
            ]
            for _, row in punctuality_issues.iterrows():
                alerts.append({
                    'type': 'info',
                    'icon': '🔍',
                    'title': 'Problema de Pontualidade',
                    'message': row['tipo_problema'],
                    'date': row.get('Data', 'N/A'),
                    'priority': 'low'
                })
        
        # Ordenar por prioridade e data
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(key=lambda x: (priority_order.get(x['priority'], 0), x['date']), reverse=True)
        
        return alerts[:10]  # Máximo 10 alertas 
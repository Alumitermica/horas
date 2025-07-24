import pandas as pd
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import streamlit as st

class DayTypeManager:
    """
    Classe responsável pela gestão avançada de tipos de dia:
    - Classificação automática de dias
    - Gestão de exceções (férias, faltas, meio-dia)
    - Validação de padrões de trabalho
    - Cálculos específicos por tipo de dia
    """
    
    def __init__(self):
        """Inicializa o gestor de tipos de dia."""
        self.day_types = {
            'Normal': {
                'description': 'Dia normal de trabalho',
                'requires_full_schedule': True,
                'expected_hours': 8.0,
                'color': '#28a745',  # Verde
                'icon': '✅'
            },
            'Meio-dia': {
                'description': 'Trabalho apenas meio-dia',
                'requires_full_schedule': False,
                'expected_hours': 4.0,
                'color': '#ffc107',  # Amarelo
                'icon': '🕐'
            },
            'Férias': {
                'description': 'Dia de férias',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#17a2b8',  # Azul
                'icon': '🏖️'
            },
            'Falta Justificada': {
                'description': 'Falta com justificação',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#6c757d',  # Cinzento
                'icon': '📋'
            },
            'Falta Não Justificada': {
                'description': 'Falta sem justificação',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#dc3545',  # Vermelho
                'icon': '❌'
            },
            'Baixa Médica': {
                'description': 'Baixa por motivos médicos',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#6f42c1',  # Roxo
                'icon': '🏥'
            },
            'Feriado': {
                'description': 'Feriado nacional/local',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#fd7e14',  # Laranja
                'icon': '🎉'
            },
            'Formação': {
                'description': 'Dia de formação/treino',
                'requires_full_schedule': True,
                'expected_hours': 8.0,
                'color': '#20c997',  # Verde-azulado
                'icon': '📚'
            },
            'Trabalho Remoto': {
                'description': 'Trabalho em casa/remoto',
                'requires_full_schedule': True,
                'expected_hours': 8.0,
                'color': '#e83e8c',  # Rosa
                'icon': '🏠'
            },
            'Compensação': {
                'description': 'Dia de compensação de horas',
                'requires_full_schedule': False,
                'expected_hours': 0.0,
                'color': '#6610f2',  # Índigo
                'icon': '⚖️'
            }
        }
        
        # Regras de detecção automática
        self.auto_detection_rules = {
            'Normal': self._detect_normal_day,
            'Meio-dia': self._detect_half_day,
            'Falta Não Justificada': self._detect_unjustified_absence
        }
    
    def get_day_types(self) -> Dict[str, Dict]:
        """Retorna todos os tipos de dia disponíveis."""
        return self.day_types
    
    def get_day_type_info(self, day_type: str) -> Dict:
        """Obtém informações sobre um tipo de dia específico."""
        return self.day_types.get(day_type, self.day_types['Normal'])
    
    def classify_day_automatically(self, row: pd.Series) -> str:
        """
        Classifica automaticamente o tipo de dia baseado nos dados.
        
        Args:
            row: Linha do DataFrame com dados de picagens
            
        Returns:
            String com o tipo de dia detectado
        """
        # Se já tem tipo definido manualmente, manter
        if 'Tipo' in row and pd.notna(row['Tipo']) and row['Tipo'] != '':
            return row['Tipo']
        
        # Executar regras de detecção automática
        for day_type, detection_func in self.auto_detection_rules.items():
            if detection_func(row):
                return day_type
        
        return 'Normal'  # Default
    
    def _detect_normal_day(self, row: pd.Series) -> bool:
        """Detecta se é um dia normal de trabalho."""
        valid_punches = self._count_valid_punches(row)
        
        # Dia normal tem 2, 4, 6 ou 8 picagens válidas
        return valid_punches in [2, 4, 6, 8] and self._has_reasonable_work_hours(row)
    
    def _detect_half_day(self, row: pd.Series) -> bool:
        """Detecta se é um meio-dia de trabalho."""
        valid_punches = self._count_valid_punches(row)
        
        if valid_punches != 2:
            return False
        
        # Calcular horas trabalhadas
        timestamps = self._extract_valid_timestamps(row)
        if len(timestamps) == 2:
            start_time = timestamps[0]
            end_time = timestamps[1]
            
            # Calcular duração
            duration = self._calculate_duration_hours(start_time, end_time)
            
            # Meio-dia: entre 3.5 e 5 horas
            return 3.5 <= duration <= 5.0
        
        return False
    
    def _detect_unjustified_absence(self, row: pd.Series) -> bool:
        """Detecta falta não justificada (sem picagens válidas)."""
        valid_punches = self._count_valid_punches(row)
        
        # Sem picagens válidas num dia que deveria ser de trabalho
        if valid_punches == 0:
            # Verificar se é dia da semana (não fim de semana)
            if 'Data' in row and pd.notna(row['Data']):
                try:
                    date = pd.to_datetime(row['Data'])
                    return date.weekday() < 5  # Segunda a sexta
                except:
                    pass
        
        return False
    
    def _count_valid_punches(self, row: pd.Series) -> int:
        """Conta o número de picagens válidas numa linha."""
        punch_columns = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
        count = 0
        
        for col in punch_columns:
            if col in row:
                value = row[col]
                if pd.notna(value) and str(value).strip() not in ['', '00:00', '0:00']:
                    try:
                        # Tentar converter para time para validar
                        if isinstance(value, str):
                            datetime.strptime(value, '%H:%M')
                        count += 1
                    except ValueError:
                        pass
        
        return count
    
    def _extract_valid_timestamps(self, row: pd.Series) -> List[str]:
        """Extrai timestamps válidos de uma linha."""
        punch_columns = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
        timestamps = []
        
        for col in punch_columns:
            if col in row:
                value = row[col]
                if pd.notna(value) and str(value).strip() not in ['', '00:00', '0:00']:
                    try:
                        # Validar formato
                        if isinstance(value, str):
                            datetime.strptime(value, '%H:%M')
                            timestamps.append(value)
                    except ValueError:
                        pass
        
        return timestamps
    
    def _calculate_duration_hours(self, start_time: str, end_time: str) -> float:
        """Calcula duração em horas entre dois horários."""
        try:
            start = datetime.strptime(start_time, '%H:%M').time()
            end = datetime.strptime(end_time, '%H:%M').time()
            
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            
            # Se end < start, assume que passou da meia-noite
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            duration_minutes = end_minutes - start_minutes
            return duration_minutes / 60.0
            
        except ValueError:
            return 0.0
    
    def _has_reasonable_work_hours(self, row: pd.Series) -> bool:
        """Verifica se as horas de trabalho são razoáveis."""
        timestamps = self._extract_valid_timestamps(row)
        
        if len(timestamps) < 2:
            return False
        
        # Calcular total de horas (simples: primeira até última picagem)
        total_hours = self._calculate_duration_hours(timestamps[0], timestamps[-1])
        
        # Horas razoáveis: entre 6 e 12 horas
        return 6.0 <= total_hours <= 12.0
    
    def calculate_expected_metrics(self, row: pd.Series, day_type: str) -> Dict:
        """
        Calcula métricas esperadas para um tipo de dia.
        
        Args:
            row: Linha do DataFrame
            day_type: Tipo de dia
            
        Returns:
            Dict com métricas calculadas
        """
        day_info = self.get_day_type_info(day_type)
        timestamps = self._extract_valid_timestamps(row)
        
        metrics = {
            'expected_hours': day_info['expected_hours'],
            'actual_hours': 0.0,
            'compliance': True,
            'alerts': [],
            'status': day_info['icon'],
            'color': day_info['color']
        }
        
        # Calcular horas reais se há picagens
        if timestamps:
            if len(timestamps) >= 2:
                # Cálculo simples: primeira até última picagem menos pausas
                total_span = self._calculate_duration_hours(timestamps[0], timestamps[-1])
                
                # Estimar pausas (almoço + intervalos)
                estimated_breaks = self._estimate_break_time(timestamps)
                metrics['actual_hours'] = max(0, total_span - estimated_breaks)
        
        # Verificar conformidade
        if day_info['requires_full_schedule']:
            expected = day_info['expected_hours']
            actual = metrics['actual_hours']
            
            # Tolerância de 30 minutos
            tolerance = 0.5
            
            if actual < (expected - tolerance):
                metrics['compliance'] = False
                metrics['alerts'].append(f"Poucas horas: {actual:.1f}h < {expected}h")
                metrics['status'] = '⚠️'
                metrics['color'] = '#ffc107'
            
            elif actual > (expected + 1.0):  # Mais de 1h extra
                metrics['alerts'].append(f"Horas extra: {actual:.1f}h > {expected}h")
                metrics['status'] = '⏰'
        
        else:
            # Tipos que não requerem horário completo
            if timestamps and day_type in ['Férias', 'Falta Justificada', 'Feriado']:
                metrics['alerts'].append("Picagens inesperadas para este tipo de dia")
                metrics['compliance'] = False
                metrics['status'] = '🤔'
                metrics['color'] = '#ffc107'
        
        return metrics
    
    def _estimate_break_time(self, timestamps: List[str]) -> float:
        """Estima tempo total de pausas baseado no número de picagens."""
        num_punches = len(timestamps)
        
        if num_punches <= 2:
            return 0.0  # Sem pausas
        elif num_punches <= 4:
            return 1.0  # ~1h almoço
        elif num_punches <= 6:
            return 1.25  # Almoço + 1 pausa
        else:
            return 1.5  # Almoço + múltiplas pausas
    
    def create_day_type_summary(self, df: pd.DataFrame) -> Dict:
        """
        Cria resumo de tipos de dia para um DataFrame.
        
        Args:
            df: DataFrame com dados processados
            
        Returns:
            Dict com resumo dos tipos de dia
        """
        if df.empty:
            return {}
        
        # Classificar todos os dias automaticamente se necessário
        df_copy = df.copy()
        df_copy['Tipo_Calculado'] = df_copy.apply(self.classify_day_automatically, axis=1)
        
        # Usar tipo calculado se tipo original estiver vazio
        df_copy['Tipo_Final'] = df_copy.apply(
            lambda row: row['Tipo'] if pd.notna(row.get('Tipo', '')) and row.get('Tipo', '') != '' 
            else row['Tipo_Calculado'], 
            axis=1
        )
        
        # Contar tipos
        type_counts = df_copy['Tipo_Final'].value_counts().to_dict()
        
        # Calcular métricas por tipo
        summary = {}
        for day_type, count in type_counts.items():
            day_info = self.get_day_type_info(day_type)
            
            # Filtrar linhas deste tipo
            type_rows = df_copy[df_copy['Tipo_Final'] == day_type]
            
            # Calcular métricas
            total_hours = 0
            compliant_days = 0
            total_alerts = 0
            
            for _, row in type_rows.iterrows():
                metrics = self.calculate_expected_metrics(row, day_type)
                total_hours += metrics['actual_hours']
                if metrics['compliance']:
                    compliant_days += 1
                total_alerts += len(metrics['alerts'])
            
            summary[day_type] = {
                'count': count,
                'info': day_info,
                'total_hours': total_hours,
                'avg_hours': total_hours / count if count > 0 else 0,
                'compliance_rate': compliant_days / count if count > 0 else 0,
                'total_alerts': total_alerts
            }
        
        return summary
    
    def create_streamlit_day_type_interface(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria interface Streamlit para gestão de tipos de dia.
        
        Args:
            df: DataFrame atual
            
        Returns:
            DataFrame atualizado
        """
        st.write("### 📅 Gestão de Tipos de Dia")
        
        # Mostrar resumo de tipos
        summary = self.create_day_type_summary(df)
        
        if summary:
            st.write("#### 📊 Resumo de Tipos de Dia")
            
            # Criar cards para cada tipo
            cols = st.columns(min(len(summary), 4))
            
            for i, (day_type, data) in enumerate(summary.items()):
                with cols[i % 4]:
                    info = data['info']
                    compliance_pct = data['compliance_rate'] * 100
                    
                    # Card colorido
                    st.markdown(f"""
                    <div style="
                        background: linear-gradient(135deg, {info['color']}20, {info['color']}40);
                        border-left: 4px solid {info['color']};
                        padding: 1rem;
                        border-radius: 8px;
                        margin: 0.5rem 0;
                    ">
                        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                            <span style="font-size: 1.5rem; margin-right: 0.5rem;">{info['icon']}</span>
                            <strong>{day_type}</strong>
                        </div>
                        <div style="font-size: 0.9rem; color: #666;">
                            📊 {data['count']} dias<br/>
                            ⏰ {data['avg_hours']:.1f}h médias<br/>
                            ✅ {compliance_pct:.0f}% conformidade
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Interface para edição em massa
        st.write("#### ✏️ Edição de Tipos de Dia")
        
        with st.expander("📝 Alterar tipos de dia em massa"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Filtro por data
                if 'Data' in df.columns:
                    dates = df['Data'].dt.date.unique() if not df.empty else []
                    selected_dates = st.multiselect(
                        "Selecionar datas:",
                        options=sorted(dates),
                        help="Escolha uma ou mais datas para alterar o tipo"
                    )
            
            with col2:
                # Novo tipo
                new_type = st.selectbox(
                    "Novo tipo de dia:",
                    options=list(self.day_types.keys()),
                    help="Tipo que será aplicado às datas selecionadas"
                )
            
            with col3:
                st.write("")  # Espaçamento
                st.write("")  # Espaçamento
                if st.button("🔄 Aplicar Alterações", help="Aplicar novo tipo às datas selecionadas"):
                    if selected_dates:
                        # Aplicar alterações
                        mask = df['Data'].dt.date.isin(selected_dates)
                        df.loc[mask, 'Tipo'] = new_type
                        
                        st.success(f"✅ Tipo '{new_type}' aplicado a {len(selected_dates)} dias!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione pelo menos uma data!")
        
        # Detecção automática
        st.write("#### 🤖 Detecção Automática")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 Executar Detecção Automática", help="Classifica automaticamente dias sem tipo definido"):
                updated_count = 0
                
                for index, row in df.iterrows():
                    current_type = row.get('Tipo', '')
                    if pd.isna(current_type) or current_type == '':
                        new_type = self.classify_day_automatically(row)
                        if new_type != 'Normal':  # Só atualizar se detectou algo específico
                            df.loc[index, 'Tipo'] = new_type
                            updated_count += 1
                
                if updated_count > 0:
                    st.success(f"✅ {updated_count} dias classificados automaticamente!")
                    st.rerun()
                else:
                    st.info("ℹ️ Nenhuma alteração necessária")
        
        with col2:
            if st.button("📋 Mostrar Tipos Disponíveis", help="Ver descrição de todos os tipos"):
                for day_type, info in self.day_types.items():
                    st.markdown(f"**{info['icon']} {day_type}:** {info['description']}")
        
        return df 
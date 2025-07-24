import pandas as pd
from datetime import datetime, timedelta
import numpy as np

class IntervalAnalyzer:
    """
    Classe responsável pela análise detalhada de intervalos de trabalho,
    incluindo pausas, almoços e validação de limites configuráveis.
    """
    
    def __init__(self, rules=None):
        """Inicializa o analisador com regras específicas."""
        self.default_rules = {
            'intervalo_almoco_minimo': 30,  # minutos
            'intervalo_almoco_maximo': 120,  # minutos
            'pausa_maxima': 15,  # minutos
            'tolerancia_intervalo': 5,  # minutos de tolerância
            'alerta_almoco_curto': 30,
            'alerta_almoco_longo': 90,
            'alerta_pausa_longa': 20
        }
        
        if rules:
            self.default_rules.update(rules)
    
    def analyze_intervals(self, df, rules=None):
        """
        Analisa intervalos detalhadamente para cada linha do DataFrame.
        
        Args:
            df: DataFrame com colunas E1, S1, E2, S2, etc.
            rules: Regras específicas para validação
            
        Returns:
            DataFrame enriquecido com análise de intervalos
        """
        if df.empty:
            return df
        
        # Usar regras fornecidas ou padrão
        current_rules = rules or self.default_rules
        
        # Criar colunas para análise detalhada
        interval_columns = {
            'periodo_manha': pd.Timedelta(0),
            'intervalo_lanche': pd.Timedelta(0),
            'intervalo_almoco': pd.Timedelta(0),
            'periodo_tarde': pd.Timedelta(0),
            'total_trabalho': pd.Timedelta(0),
            'total_pausas': pd.Timedelta(0),
            'duracao_almoco': pd.Timedelta(0),
            'duracao_pausa_manha': pd.Timedelta(0),
            'duracao_pausa_tarde': pd.Timedelta(0),
            'total_pausas_dia': pd.Timedelta(0),
            'alerta_intervalos': '',
            'conformidade_intervalos': True,
            'detalhes_intervalos': ''
        }
        
        for col, default in interval_columns.items():
            if col not in df.columns:
                df[col] = default
        
        # Analisar cada linha
        for index, row in df.iterrows():
            interval_analysis = self._analyze_row_intervals(row, current_rules)
            
            # Aplicar resultados da análise
            for key, value in interval_analysis.items():
                if key in df.columns:
                    df.loc[index, key] = value
        
        return df
    
    def _analyze_row_intervals(self, row, rules):
        """Analisa intervalos para uma linha específica."""
        # Coletar timestamps válidos
        timestamps = self._extract_valid_timestamps(row)
        
        if len(timestamps) < 4:
            return {
                'duracao_almoco': pd.Timedelta(0),
                'duracao_pausa_manha': pd.Timedelta(0),
                'duracao_pausa_tarde': pd.Timedelta(0),
                'total_pausas_dia': pd.Timedelta(0),
                'alerta_intervalos': 'Timestamps insuficientes para análise',
                'conformidade_intervalos': False,
                'detalhes_intervalos': f'Apenas {len(timestamps)} timestamps válidos'
            }
        
        # Analisar baseado no número de timestamps
        if len(timestamps) == 3:
            return self._analyze_3_timestamps(timestamps, rules)
        elif len(timestamps) == 4:
            return self._analyze_4_timestamps(timestamps, rules)
        elif len(timestamps) == 6:
            return self._analyze_6_timestamps(timestamps, rules)
        elif len(timestamps) == 8:
            return self._analyze_8_timestamps(timestamps, rules)
        else:
            return self._analyze_irregular_timestamps(timestamps, rules)
    
    def _extract_valid_timestamps(self, row):
        """Extrai timestamps válidos de uma linha."""
        time_columns = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
        timestamps = []
        
        for col in time_columns:
            if col in row and pd.notna(row[col]):
                time_str = str(row[col]).strip()
                if time_str and time_str != '00:00' and time_str != 'nan':
                    # Converter para objeto time para cálculos
                    try:
                        time_obj = datetime.strptime(time_str, '%H:%M').time()
                        timestamps.append(time_obj)
                    except ValueError:
                        continue
        
        return timestamps
    
    def _analyze_3_timestamps(self, timestamps, rules):
        """Analisa padrão incompleto E1-S1-E2 (3 timestamps) - falta saída final."""
        e1, s1, e2 = timestamps
        
        # PADRÃO INCOMPLETO: E1=entrada, S1=saída almoço, E2=entrada almoço, FALTA S2=saída final
        
        # Calcular duração do almoço (S1 até E2)
        almoco_duration = self._calculate_time_difference(s1, e2)
        almoco_minutos = almoco_duration.total_seconds() / 60
        
        # Calcular período de manhã (E1 até S1)
        periodo_manha = self._calculate_time_difference(e1, s1)
        
        # Verificar conformidade do almoço
        alerta_almoco_curto = rules.get('alerta_almoco_curto', 25)
        alerta_almoco_longo = rules.get('alerta_almoco_longo', 75)
        
        alertas = ['Padrão incompleto: falta saída final (S2)']
        if almoco_minutos < alerta_almoco_curto:
            alertas.append(f"Almoço muito curto ({almoco_minutos:.0f}min)")
        elif almoco_minutos > alerta_almoco_longo:
            alertas.append(f"Almoço muito longo ({almoco_minutos:.0f}min)")
        
        # Padrão incompleto = não conforme
        conformidade = False
        
        return {
            'periodo_manha': periodo_manha,
            'intervalo_lanche': pd.Timedelta(0),  # Não aplicável
            'intervalo_almoco': almoco_duration,
            'periodo_tarde': pd.Timedelta(0),  # Não calculável sem saída final
            'total_trabalho': periodo_manha,  # Apenas período da manhã calculável
            'total_pausas': almoco_duration,
            'duracao_almoco': almoco_duration,
            'duracao_pausa_manha': pd.Timedelta(0),  # Não aplicável
            'duracao_pausa_tarde': pd.Timedelta(0),  # Não aplicável
            'total_pausas_dia': almoco_duration,
            'alerta_intervalos': '; '.join(alertas),
            'conformidade_intervalos': conformidade,
            'detalhes_intervalos': f'⚠️ Padrão incompleto (3/4 picagens): falta saída final. Manhã: {self.format_timedelta_to_minutes(periodo_manha)}, Almoço: {self.format_timedelta_to_minutes(almoco_duration)}'
        }
    
    def _analyze_4_timestamps(self, timestamps, rules):
        """
        Analisa padrão básico E1-S1-E2-S2 (4 timestamps).
        
        PADRÃO: Trabalho com apenas pausa para almoço
        - E1: Entrada manhã - S1: Saída almoço - E2: Entrada almoço - S2: Saída final
        """
        e1, s1, e2, s2 = timestamps
        
        # Calcular duração do almoço (S1 até E2)
        almoco_duration = self._calculate_time_difference(s1, e2)
        
        # Gerar alertas
        alertas = []
        detalhes = []
        conformidade = True
        
        # Validar duração do almoço
        almoco_minutos = almoco_duration.total_seconds() / 60
        
        if almoco_minutos < rules['alerta_almoco_curto']:
            alertas.append(f'Almoço muito curto ({almoco_minutos:.0f}min)')
            conformidade = False
        elif almoco_minutos > rules['alerta_almoco_longo']:
            alertas.append(f'Almoço muito longo ({almoco_minutos:.0f}min)')
            conformidade = False
        
        # Detalhes da análise
        detalhes.append(f'🌅 Manhã: {e1.strftime("%H:%M")}-{s1.strftime("%H:%M")}')
        detalhes.append(f'🍽️ Almoço: {s1.strftime("%H:%M")}-{e2.strftime("%H:%M")} ({almoco_minutos:.0f}min)')
        detalhes.append(f'🌆 Tarde: {e2.strftime("%H:%M")}-{s2.strftime("%H:%M")}')
        detalhes.append(f'📋 Padrão: 4 picagens (apenas almoço)')
        
        # Calcular períodos de trabalho
        periodo_manha = self._calculate_time_difference(e1, s1)
        periodo_tarde = self._calculate_time_difference(e2, s2)
        total_trabalho = periodo_manha + periodo_tarde
        
        return {
            'periodo_manha': periodo_manha,
            'intervalo_lanche': pd.Timedelta(0),  # Não aplicável
            'intervalo_almoco': almoco_duration,
            'periodo_tarde': periodo_tarde,
            'total_trabalho': total_trabalho,
            'total_pausas': almoco_duration,
            'duracao_almoco': almoco_duration,
            'duracao_pausa_manha': pd.Timedelta(0),
            'duracao_pausa_tarde': pd.Timedelta(0),
            'total_pausas_dia': almoco_duration,
            'alerta_intervalos': '; '.join(alertas) if alertas else '',
            'conformidade_intervalos': conformidade,
            'detalhes_intervalos': ' | '.join(detalhes)
        }
    
    def _analyze_6_timestamps(self, timestamps, rules):
        """
        Analisa padrão com intervalo manhã E1-S1-E2-S2-E3-S3 (6 timestamps).
        
        PADRÃO: Trabalho com lanche manhã + almoço
        - E1: Entrada - S1: Saída lanche manhã - E2: Entrada lanche - S2: Saída almoço - E3: Entrada almoço - S3: Saída final
        """
        e1, s1, e2, s2, e3, s3 = timestamps
        
        # Calcular durações
        pausa1_duration = self._calculate_time_difference(s1, e2)  # Lanche manhã
        almoco_duration = self._calculate_time_difference(s2, e3)  # Almoço
        
        # Gerar alertas
        alertas = []
        detalhes = []
        conformidade = True
        
        # Validar primeira pausa
        pausa1_minutos = pausa1_duration.total_seconds() / 60
        if pausa1_minutos > rules['alerta_pausa_longa']:
            alertas.append(f'Pausa manhã muito longa ({pausa1_minutos:.0f}min)')
            conformidade = False
        
        # Validar almoço
        almoco_minutos = almoco_duration.total_seconds() / 60
        if almoco_minutos < rules['alerta_almoco_curto']:
            alertas.append(f'Almoço muito curto ({almoco_minutos:.0f}min)')
            conformidade = False
        elif almoco_minutos > rules['alerta_almoco_longo']:
            alertas.append(f'Almoço muito longo ({almoco_minutos:.0f}min)')
            conformidade = False
        
        # Detalhes da análise  
        detalhes.append(f'🌅 Manhã início: {e1.strftime("%H:%M")}-{s1.strftime("%H:%M")}')
        detalhes.append(f'☕ Lanche manhã: {s1.strftime("%H:%M")}-{e2.strftime("%H:%M")} ({pausa1_minutos:.0f}min)')
        detalhes.append(f'🌅 Manhã fim: {e2.strftime("%H:%M")}-{s2.strftime("%H:%M")}')
        detalhes.append(f'🍽️ Almoço: {s2.strftime("%H:%M")}-{e3.strftime("%H:%M")} ({almoco_minutos:.0f}min)')
        detalhes.append(f'🌆 Tarde: {e3.strftime("%H:%M")}-{s3.strftime("%H:%M")}')
        detalhes.append(f'📋 Padrão: 6 picagens (lanche manhã + almoço)')
        
        total_pausas = pausa1_duration + almoco_duration
        
        return {
            'duracao_almoco': almoco_duration,
            'duracao_pausa_manha': pausa1_duration,
            'duracao_pausa_tarde': pd.Timedelta(0),
            'total_pausas_dia': total_pausas,
            'alerta_intervalos': '; '.join(alertas) if alertas else '',
            'conformidade_intervalos': conformidade,
            'detalhes_intervalos': ' | '.join(detalhes)
        }
    
    def _analyze_8_timestamps(self, timestamps, rules):
        """
        Analisa padrão completo E1-S1-E2-S2-E3-S3-E4-S4 (8 timestamps).
        
        PADRÃO: Trabalho com lanche manhã + almoço + lanche tarde  
        - E1: Entrada - S1: Saída lanche manhã - E2: Entrada - S2: Saída almoço 
        - E3: Entrada almoço - S3: Saída lanche tarde - E4: Entrada - S4: Saída final
        """
        e1, s1, e2, s2, e3, s3, e4, s4 = timestamps
        
        # Calcular durações
        pausa1_duration = self._calculate_time_difference(s1, e2)  # Lanche manhã
        pausa2_duration = self._calculate_time_difference(s2, e3)  # Almoço  
        pausa3_duration = self._calculate_time_difference(s3, e4)  # Lanche tarde
        
        # Identificar qual é o almoço (maior pausa)
        pausas = [
            ('Pausa 1', pausa1_duration, s1, e2),
            ('Pausa 2', pausa2_duration, s2, e3),
            ('Pausa 3', pausa3_duration, s3, e4)
        ]
        
        # Ordenar por duração para identificar o almoço
        pausas_ordenadas = sorted(pausas, key=lambda x: x[1], reverse=True)
        almoco_info = pausas_ordenadas[0]  # Maior pausa = almoço
        
        # Gerar alertas
        alertas = []
        detalhes = []
        conformidade = True
        
        # Criar detalhes visuais primeiro
        detalhes.append(f'🌅 Manhã início: {e1.strftime("%H:%M")}-{s1.strftime("%H:%M")}')
        detalhes.append(f'☕ Lanche manhã: {s1.strftime("%H:%M")}-{e2.strftime("%H:%M")} ({pausa1_duration.total_seconds()/60:.0f}min)')
        detalhes.append(f'🌅 Manhã fim: {e2.strftime("%H:%M")}-{s2.strftime("%H:%M")}')
        detalhes.append(f'🍽️ Almoço: {s2.strftime("%H:%M")}-{e3.strftime("%H:%M")} ({pausa2_duration.total_seconds()/60:.0f}min)')
        detalhes.append(f'🌆 Tarde início: {e3.strftime("%H:%M")}-{s3.strftime("%H:%M")}')
        detalhes.append(f'☕ Lanche tarde: {s3.strftime("%H:%M")}-{e4.strftime("%H:%M")} ({pausa3_duration.total_seconds()/60:.0f}min)')
        detalhes.append(f'🌆 Tarde fim: {e4.strftime("%H:%M")}-{s4.strftime("%H:%M")}')
        detalhes.append(f'📋 Padrão: 8 picagens (lanche manhã + almoço + lanche tarde)')
        
        # Validar cada pausa
        for nome, duracao, inicio, fim in pausas:
            minutos = duracao.total_seconds() / 60
            
            if nome == almoco_info[0]:  # É o almoço
                if minutos < rules['alerta_almoco_curto']:
                    alertas.append(f'Almoço muito curto ({minutos:.0f}min)')
                    conformidade = False
                elif minutos > rules['alerta_almoco_longo']:
                    alertas.append(f'Almoço muito longo ({minutos:.0f}min)')
                    conformidade = False
            else:  # É pausa normal
                if minutos > rules['alerta_pausa_longa']:
                    alertas.append(f'{nome} muito longa ({minutos:.0f}min)')
                    conformidade = False
        
        total_pausas = pausa1_duration + pausa2_duration + pausa3_duration
        
        return {
            'duracao_almoco': pausa2_duration,  # Pausa 2 é sempre o almoço (meio do dia)
            'duracao_pausa_manha': pausa1_duration,  # Lanche manhã
            'duracao_pausa_tarde': pausa3_duration,  # Lanche tarde
            'total_pausas_dia': total_pausas,
            'alerta_intervalos': '; '.join(alertas) if alertas else '',
            'conformidade_intervalos': conformidade,
            'detalhes_intervalos': ' | '.join(detalhes)
        }
    
    def _analyze_irregular_timestamps(self, timestamps, rules):
        """Analisa padrões irregulares de timestamps."""
        return {
            'duracao_almoco': pd.Timedelta(0),
            'duracao_pausa_manha': pd.Timedelta(0),
            'duracao_pausa_tarde': pd.Timedelta(0),
            'total_pausas_dia': pd.Timedelta(0),
            'alerta_intervalos': f'Padrão irregular: {len(timestamps)} timestamps',
            'conformidade_intervalos': False,
            'detalhes_intervalos': f'Análise não suportada para {len(timestamps)} timestamps'
        }
    
    def _calculate_time_difference(self, start_time, end_time):
        """Calcula diferença entre dois objetos time, retornando Timedelta."""
        # Converter time objects para datetime para cálculos
        base_date = datetime.today().date()
        start_dt = datetime.combine(base_date, start_time)
        end_dt = datetime.combine(base_date, end_time)
        
        # Se end_time é menor que start_time, assumir que é no dia seguinte
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        
        return end_dt - start_dt
    
    def generate_interval_summary(self, df):
        """Gera resumo estatístico dos intervalos."""
        if df.empty or 'duracao_almoco' not in df.columns:
            return {}
        
        # Filtrar apenas dias com dados válidos
        valid_days = df[df['conformidade_intervalos'] == True]
        
        if valid_days.empty:
            return {'error': 'Nenhum dia com intervalos válidos encontrado'}
        
        # Calcular estatísticas
        almoco_stats = {
            'media': valid_days['duracao_almoco'].mean(),
            'minimo': valid_days['duracao_almoco'].min(),
            'maximo': valid_days['duracao_almoco'].max(),
            'mediana': valid_days['duracao_almoco'].median()
        }
        
        # Converter para minutos para apresentação
        for key in almoco_stats:
            if pd.notna(almoco_stats[key]):
                almoco_stats[key] = almoco_stats[key].total_seconds() / 60
        
        # Contar problemas
        problemas = {
            'dias_com_alertas': len(df[df['alerta_intervalos'] != '']),
            'dias_nao_conformes': len(df[df['conformidade_intervalos'] == False]),
            'total_dias_analisados': len(df)
        }
        
        return {
            'almoco_estatisticas': almoco_stats,
            'problemas': problemas,
            'taxa_conformidade': (problemas['total_dias_analisados'] - problemas['dias_nao_conformes']) / problemas['total_dias_analisados'] * 100
        }
    
    def format_timedelta_to_minutes(self, td):
        """Converte Timedelta para string em minutos."""
        if pd.isnull(td) or td.total_seconds() == 0:
            return "0 min"
        
        total_minutes = int(td.total_seconds() / 60)
        return f"{total_minutes} min" 
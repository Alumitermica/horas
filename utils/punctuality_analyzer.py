import pandas as pd
from datetime import datetime, time, timedelta
import numpy as np
from typing import List, Dict, Tuple, Optional

class PunctualityAnalyzer:
    """
    Classe responsável pela análise avançada de pontualidade, incluindo:
    - Detecção de picagens em falta ou esquecidas
    - Sugestões de correção automática
    - Análise de padrões de atraso
    - Interface para edição manual
    """
    
    def __init__(self, rules=None):
        """Inicializa o analisador com regras específicas."""
        self.default_rules = {
            'hora_entrada_padrao': '08:30',
            'hora_saida_padrao': '17:30',
            'tolerancia_atraso_minutos': 15,
            'duracao_almoco_padrao': 60,  # minutos
            'duracao_pausa_padrao': 15,   # minutos
            'max_diferenca_horario': 120, # minutos para detectar anomalias
        }
        
        if rules:
            self.default_rules.update(rules)
    
    def analyze_punctuality_issues(self, df, rules=None):
        """
        Analisa problemas de pontualidade e picagens em falta.
        
        Args:
            df: DataFrame com dados processados
            rules: Regras específicas do setor
            
        Returns:
            DataFrame enriquecido com análise de pontualidade
        """
        if df.empty:
            return df
        
        current_rules = rules or self.default_rules
        
        # Criar colunas para análise de pontualidade
        punctuality_columns = {
            'picagens_sugeridas': '',
            'tipo_problema': '',
            'correcao_sugerida': '',
            'confianca_sugestao': 0.0,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': False
        }
        
        for col, default in punctuality_columns.items():
            if col not in df.columns:
                df[col] = default
        
        # Analisar cada linha
        for index, row in df.iterrows():
            analysis = self._analyze_row_punctuality(row, current_rules)
            
            # Aplicar resultados
            for key, value in analysis.items():
                if key in df.columns:
                    df.loc[index, key] = value
        
        return df
    
    def _analyze_row_punctuality(self, row, rules) -> Dict:
        """Analisa pontualidade e problemas para uma linha específica."""
        # Verificar se é um tipo de dia que não requer picagens
        if 'Tipo' in row:
            tipo_dia = str(row['Tipo']).lower() if pd.notna(row['Tipo']) else ''
            if any(tipo in tipo_dia for tipo in ['folga', 'férias', 'feriado', 'ausência', 'baixa médica', 'compensação']):
                return self._create_expected_no_data_result(tipo_dia)
        
        # Verificar se é dia de trabalho baseado nas configurações
        try:
            from .config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # Obter setor (usar Departamento se disponível, senão Produção)
            sector = row.get('Departamento', 'Produção')
            
            # Verificar se é dia de trabalho
            if 'Data' in row and pd.notna(row['Data']):
                 date = pd.to_datetime(row['Data'])
                 if not config_manager.is_work_day(date, sector):
                     # Se não é dia de trabalho mas tem picagens, alertar
                     timestamps = self._extract_timestamps_with_positions(row)
                     if timestamps:
                         return {
                             'picagens_sugeridas': '',
                             'tipo_problema': 'Picagens em dia não útil',
                             'correcao_sugerida': f'Picagens encontradas em {date.strftime("%A")} - verificar se correto',
                             'confianca_sugestao': 0.8,
                             'atraso_minutos': 0,
                             'saida_antecipada_minutos': 0,
                             'requer_verificacao_manual': True
                         }
                     else:
                         return self._create_expected_no_data_result('fim de semana')
        except:
            # Se falhar, assumir lógica padrão (segunda a sexta)
            if 'Data' in row and pd.notna(row['Data']):
                try:
                    date = pd.to_datetime(row['Data'])
                    if date.weekday() >= 5:  # Sábado ou domingo
                        return self._create_expected_no_data_result('fim de semana')
                except:
                    pass
        
        # Extrair timestamps válidos
        timestamps = self._extract_timestamps_with_positions(row)
        
        if not timestamps:
            return self._create_no_data_result()
        
        # Usar ConfigManager para análise inteligente se disponível
        try:
            from .config_manager import ConfigManager
            config_manager = ConfigManager()
            
            # Obter configuração apropriada (usar Departamento se disponível)
            sector = row.get('Departamento', 'Produção')
            config = config_manager.get_sector_config(sector)
            
            # Análise inteligente usando configurações
            smart_analysis = config_manager.analyze_punch_pattern(timestamps, config)
            
            # Converter resultado para formato esperado
            return self._convert_smart_analysis_result(smart_analysis, timestamps, rules)
            
        except ImportError:
            # Fallback para análise original se ConfigManager não disponível
            pass
        
        # Detectar tipo de problema
        problem_type = self._detect_problem_type(timestamps, rules)
        
        # Gerar sugestão de correção baseada no problema
        if problem_type == 'missing_entry':
            return self._suggest_missing_entry_fix(timestamps, rules)
        elif problem_type == 'missing_exit':
            return self._suggest_missing_exit_fix(timestamps, rules)
        elif problem_type == 'odd_timestamps':
            return self._suggest_odd_timestamps_fix(timestamps, rules)
        elif problem_type == 'sequence_error':
            return self._suggest_sequence_fix(timestamps, rules)
        elif problem_type == 'late_entry':
            return self._analyze_late_entry(timestamps, rules)
        elif problem_type == 'early_exit':
            return self._analyze_early_exit(timestamps, rules)
        else:
            return self._analyze_normal_day(timestamps, rules)
    
    def _extract_timestamps_with_positions(self, row) -> List[Tuple[str, str]]:
        """Extrai timestamps com suas posições (E1, S1, etc.)."""
        time_columns = ['E1', 'S1', 'E2', 'S2', 'E3', 'S3', 'E4', 'S4']
        timestamps = []
        
        for col in time_columns:
            if col in row and pd.notna(row[col]):
                time_str = str(row[col]).strip()
                if time_str and time_str != '00:00' and time_str != 'nan':
                    timestamps.append((col, time_str))
        
        return timestamps
    
    def _detect_problem_type(self, timestamps: List[Tuple[str, str]], rules) -> str:
        """Detecta o tipo de problema com as picagens."""
        if not timestamps:
            return 'no_data'
        
        # Extrair apenas os horários
        times = [t[1] for t in timestamps]
        
        # Verificar se há número ímpar de timestamps (exceto 3 que é válido)
        if len(timestamps) % 2 != 0 and len(timestamps) != 3:
            # Análise mais detalhada para ímpar
            if len(timestamps) == 1:
                return 'single_timestamp'
            elif timestamps[0][0].startswith('S'):  # Começa com saída
                return 'missing_entry'
            elif timestamps[-1][0].startswith('E'):  # Termina com entrada
                return 'missing_exit'
            else:
                return 'odd_timestamps'
        
        # Para 3 timestamps: tratar como padrão incompleto
        if len(timestamps) == 3:
            if (timestamps[0][0] == 'E1' and 
                timestamps[1][0] == 'S1' and 
                timestamps[2][0] == 'E2'):
                # Padrão incompleto E1-S1-E2 (falta S2)
                return 'missing_exit'
            else:
                return 'invalid_3_pattern'
        
        # Verificar sequência temporal
        try:
            time_objects = [datetime.strptime(t, '%H:%M').time() for t in times]
            for i in range(1, len(time_objects)):
                if time_objects[i] <= time_objects[i-1]:
                    return 'sequence_error'
        except ValueError:
            return 'invalid_format'
        
        # Verificar atrasos significativos
        entry_time = datetime.strptime(times[0], '%H:%M').time()
        standard_entry = datetime.strptime(rules['hora_entrada_padrao'], '%H:%M').time()
        
        entry_minutes = entry_time.hour * 60 + entry_time.minute
        standard_minutes = standard_entry.hour * 60 + standard_entry.minute
        
        if entry_minutes > standard_minutes + rules['tolerancia_atraso_minutos']:
            return 'late_entry'
        
        # Verificar saídas antecipadas
        if len(times) >= 2:
            exit_time = datetime.strptime(times[-1], '%H:%M').time()
            standard_exit = datetime.strptime(rules['hora_saida_padrao'], '%H:%M').time()
            
            exit_minutes = exit_time.hour * 60 + exit_time.minute
            standard_exit_minutes = standard_exit.hour * 60 + standard_exit.minute
            
            if exit_minutes < standard_exit_minutes - rules['tolerancia_atraso_minutos']:
                return 'early_exit'
        
        return 'normal'
    
    def _suggest_missing_entry_fix(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Sugere correção para entrada em falta."""
        # Assumir que a primeira picagem deveria ser uma saída
        first_time = timestamps[0][1]
        
        # Sugerir entrada baseada no horário padrão ou calculada
        suggested_entry = rules['hora_entrada_padrao']
        
        # Se a primeira picagem for muito tarde, sugerir horário mais próximo
        first_time_obj = datetime.strptime(first_time, '%H:%M').time()
        if first_time_obj.hour >= 10:  # Se primeira picagem é após 10h
            # Sugerir entrada 1-2h antes
            suggested_minutes = (first_time_obj.hour - 2) * 60 + first_time_obj.minute
            suggested_entry = f"{suggested_minutes // 60:02d}:{suggested_minutes % 60:02d}"
        
        return {
            'picagens_sugeridas': f'Adicionar E1: {suggested_entry}',
            'tipo_problema': 'Entrada em falta',
            'correcao_sugerida': f'Inserir picagem de entrada às {suggested_entry}',
            'confianca_sugestao': 0.8,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': True
        }
    
    def _suggest_missing_exit_fix(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Sugere correção para saída em falta."""
        # Última picagem deveria ser uma entrada, falta a saída
        last_time = timestamps[-1][1]
        
        # Caso especial: 3 picagens E1-S1-E2 (falta S2)
        if (len(timestamps) == 3 and 
            timestamps[0][0] == 'E1' and 
            timestamps[1][0] == 'S1' and 
            timestamps[2][0] == 'E2'):
            
            # Sugerir S2 baseado na hora padrão de saída
            suggested_exit = rules['hora_saida_padrao']
            
            return {
                'picagens_sugeridas': f'Adicionar S2: {suggested_exit}',
                'tipo_problema': 'Saída final em falta',
                'correcao_sugerida': f'Padrão incompleto E1-S1-E2. Adicionar saída final (S2) às {suggested_exit}',
                'confianca_sugestao': 0.8,
                'atraso_minutos': 0,
                'saida_antecipada_minutos': 0,
                'requer_verificacao_manual': True
            }
        
        # Caso geral: outras situações de saída em falta
        suggested_exit = rules['hora_saida_padrao']
        
        # Se a última entrada for muito tarde, ajustar a saída
        last_time_obj = datetime.strptime(last_time, '%H:%M').time()
        if last_time_obj.hour >= 14:  # Entrada tarde da tarde
            # Sugerir saída 3-4h depois
            suggested_minutes = (last_time_obj.hour + 4) * 60 + last_time_obj.minute
            if suggested_minutes >= 24 * 60:
                suggested_minutes = 17 * 60 + 30  # Default 17:30
            suggested_exit = f"{suggested_minutes // 60:02d}:{suggested_minutes % 60:02d}"
        
        return {
            'picagens_sugeridas': f'Adicionar S{len(timestamps)//2 + 1}: {suggested_exit}',
            'tipo_problema': 'Saída em falta',
            'correcao_sugerida': f'Inserir picagem de saída às {suggested_exit}',
            'confianca_sugestao': 0.7,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': True
        }
    
    def _suggest_odd_timestamps_fix(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Sugere correção para número ímpar de timestamps."""
        count = len(timestamps)
        times = [t[1] for t in timestamps]
        
        # Análise dos intervalos para detectar o que está em falta
        if count == 3:
            # Pode faltar entrada inicial ou saída final
            time_gaps = []
            for i in range(len(times) - 1):
                gap = self._calculate_time_gap(times[i], times[i+1])
                time_gaps.append(gap)
            
            # Se primeiro gap for muito grande, pode faltar entrada
            if time_gaps[0] > 120:  # Mais de 2h
                suggested_entry = self._calculate_suggested_time(times[0], -120)  # 2h antes
                suggestion = f'Adicionar E1: {suggested_entry}'
                problem = 'Possível entrada em falta'
            else:
                # Provavelmente falta saída final
                suggested_exit = self._calculate_suggested_time(times[-1], 240)  # 4h depois
                suggestion = f'Adicionar S{count//2 + 1}: {suggested_exit}'
                problem = 'Possível saída em falta'
        
        elif count == 5:
            # Análise mais complexa - pode faltar qualquer picagem
            suggestion = 'Verificar sequência completa de picagens'
            problem = 'Sequência incompleta'
        
        else:
            suggestion = f'Verificar {count} picagens registadas'
            problem = f'{count} timestamps (número ímpar)'
        
        return {
            'picagens_sugeridas': suggestion,
            'tipo_problema': problem,
            'correcao_sugerida': 'Verificação manual necessária',
            'confianca_sugestao': 0.5,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': True
        }
    
    def _suggest_sequence_fix(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Sugere correção para problemas de sequência temporal."""
        times = [t[1] for t in timestamps]
        
        # Encontrar onde está o problema na sequência
        problem_index = -1
        for i in range(1, len(times)):
            if datetime.strptime(times[i], '%H:%M').time() <= datetime.strptime(times[i-1], '%H:%M').time():
                problem_index = i
                break
        
        return {
            'picagens_sugeridas': f'Verificar horário na posição {problem_index + 1}',
            'tipo_problema': 'Sequência temporal inválida',
            'correcao_sugerida': f'Corrigir horário {times[problem_index]} - deve ser posterior a {times[problem_index-1]}',
            'confianca_sugestao': 0.9,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': True
        }
    
    def _analyze_late_entry(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Analisa atraso na entrada."""
        entry_time = timestamps[0][1]
        standard_entry = rules['hora_entrada_padrao']
        
        entry_obj = datetime.strptime(entry_time, '%H:%M').time()
        standard_obj = datetime.strptime(standard_entry, '%H:%M').time()
        
        entry_minutes = entry_obj.hour * 60 + entry_obj.minute
        standard_minutes = standard_obj.hour * 60 + standard_obj.minute
        
        delay = entry_minutes - standard_minutes
        
        return {
            'picagens_sugeridas': '',
            'tipo_problema': 'Atraso na entrada',
            'correcao_sugerida': f'Atraso de {delay} minutos (entrada: {entry_time}, esperado: {standard_entry})',
            'confianca_sugestao': 1.0,
            'atraso_minutos': delay,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': False
        }
    
    def _analyze_early_exit(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Analisa saída antecipada."""
        exit_time = timestamps[-1][1]
        standard_exit = rules['hora_saida_padrao']
        
        exit_obj = datetime.strptime(exit_time, '%H:%M').time()
        standard_obj = datetime.strptime(standard_exit, '%H:%M').time()
        
        exit_minutes = exit_obj.hour * 60 + exit_obj.minute
        standard_minutes = standard_obj.hour * 60 + standard_obj.minute
        
        early_exit = standard_minutes - exit_minutes
        
        return {
            'picagens_sugeridas': '',
            'tipo_problema': 'Saída antecipada',
            'correcao_sugerida': f'Saída {early_exit} minutos antes (saída: {exit_time}, esperado: {standard_exit})',
            'confianca_sugestao': 1.0,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': early_exit,
            'requer_verificacao_manual': False
        }
    
    def _analyze_normal_day(self, timestamps: List[Tuple[str, str]], rules) -> Dict:
        """Analisa dia normal sem problemas evidentes."""
        return {
            'picagens_sugeridas': '',
            'tipo_problema': '',
            'correcao_sugerida': '',
            'confianca_sugestao': 1.0,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': False
        }
    
    def _create_no_data_result(self) -> Dict:
        """Resultado para linhas sem dados."""
        return {
            'picagens_sugeridas': 'Nenhuma picagem registada',
            'tipo_problema': 'Sem dados',
            'correcao_sugerida': 'Inserir picagens manualmente',
            'confianca_sugestao': 0.0,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': True
        }
    
    def _create_expected_no_data_result(self, tipo_dia: str) -> Dict:
        """Resultado para dias onde não são esperadas picagens (folgas, férias, etc.)."""
        return {
            'picagens_sugeridas': '',
            'tipo_problema': '',
            'correcao_sugerida': f'Dia de {tipo_dia} - picagens não requeridas',
            'confianca_sugestao': 1.0,
            'atraso_minutos': 0,
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': False
        }
    
    def _calculate_time_gap(self, time1: str, time2: str) -> int:
        """Calcula diferença em minutos entre dois horários."""
        t1 = datetime.strptime(time1, '%H:%M').time()
        t2 = datetime.strptime(time2, '%H:%M').time()
        
        minutes1 = t1.hour * 60 + t1.minute
        minutes2 = t2.hour * 60 + t2.minute
        
        return minutes2 - minutes1
    
    def _calculate_suggested_time(self, base_time: str, offset_minutes: int) -> str:
        """Calcula horário sugerido baseado num offset."""
        base = datetime.strptime(base_time, '%H:%M').time()
        base_minutes = base.hour * 60 + base.minute
        
        new_minutes = base_minutes + offset_minutes
        
        # Limitar a 24h
        if new_minutes < 0:
            new_minutes = 8 * 60  # Default 08:00
        elif new_minutes >= 24 * 60:
            new_minutes = 17 * 60 + 30  # Default 17:30
        
        hours = new_minutes // 60
        minutes = new_minutes % 60
        
        return f"{hours:02d}:{minutes:02d}"
    
    def generate_punctuality_patterns(self, df) -> Dict:
        """Gera análise de padrões de pontualidade."""
        if df.empty:
            return {}
        
        # Filtrar dias com dados válidos
        valid_days = df[df['atraso_minutos'].notna()].copy()
        
        if valid_days.empty:
            return {'error': 'Nenhum dado de pontualidade válido'}
        
        # Análise de padrões
        patterns = {
            'atraso_medio': valid_days['atraso_minutos'].mean(),
            'dias_com_atraso': len(valid_days[valid_days['atraso_minutos'] > 0]),
            'maior_atraso': valid_days['atraso_minutos'].max(),
            'atrasos_por_dia_semana': {},
            'tendencia_atraso': self._calculate_trend(valid_days)
        }
        
        # Atrasos por dia da semana
        if 'Data' in valid_days.columns:
            valid_days['dia_semana'] = valid_days['Data'].dt.day_name()
            patterns['atrasos_por_dia_semana'] = valid_days.groupby('dia_semana')['atraso_minutos'].mean().to_dict()
        
        return patterns
    
    def _calculate_trend(self, df) -> str:
        """Calcula tendência de atraso ao longo do tempo."""
        if len(df) < 5:
            return 'Dados insuficientes'
        
        # Análise simples: comparar primeira e segunda metade
        mid_point = len(df) // 2
        first_half = df.iloc[:mid_point]['atraso_minutos'].mean()
        second_half = df.iloc[mid_point:]['atraso_minutos'].mean()
        
        if second_half > first_half + 2:
            return 'Piorando'
        elif first_half > second_half + 2:
            return 'Melhorando'
        else:
                         return 'Estável'
    
    def _convert_smart_analysis_result(self, smart_analysis: Dict, timestamps: List[Tuple[str, str]], rules: Dict) -> Dict:
        """Converte resultado da análise inteligente para formato esperado."""
        tipo_analise = smart_analysis.get('tipo_analise', '')
        confianca = smart_analysis.get('confianca', 0.0)
        sugestao = smart_analysis.get('sugestao', '')
        detalhes = smart_analysis.get('detalhes', '')
        
        # Mapear tipos de análise para tipos de problema
        problem_mapping = {
            'esqueceu_entrada': 'Entrada em falta',
            'esqueceu_saida': 'Saída em falta',
            'possivel_esquecimento_entrada': 'Possível esquecimento de entrada',
            'atraso_normal': 'Atraso na entrada',
            'sem_dados': 'Sem dados',
            'normal': '',
            'padrao_irregular': 'Padrão irregular'
        }
        
        tipo_problema = problem_mapping.get(tipo_analise, tipo_analise)
        
        # Calcular atraso se disponível
        atraso_minutos = 0
        if tipo_analise in ['atraso_normal', 'possivel_esquecimento_entrada']:
            if timestamps and 'hora_entrada_padrao' in rules:
                try:
                    first_time = timestamps[0][1]
                    standard_time = rules['hora_entrada_padrao']
                    atraso_minutos = self._calculate_time_gap(standard_time, first_time)
                except:
                    pass
        
        return {
            'picagens_sugeridas': sugestao,
            'tipo_problema': tipo_problema,
            'correcao_sugerida': detalhes,
            'confianca_sugestao': confianca,
            'atraso_minutos': max(0, atraso_minutos),
            'saida_antecipada_minutos': 0,
            'requer_verificacao_manual': confianca < 0.9 and tipo_problema != ''
        } 
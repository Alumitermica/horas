import json
import pandas as pd
from datetime import datetime, timedelta

class RulesEngine:
    def __init__(self):
        self.default_rules = {
            "horas_diarias_objetivo": 8.0,
            "tolerancia_atraso_minutos": 15,
            "hora_entrada_padrao": "08:30",
            "hora_saida_padrao": "17:30",
            "intervalo_almoco_minimo": 30,
            "max_horas_extras_dia": 2.0,
            "min_intervalo_turnos": 11,  # horas
            "dias_trabalho_semana": 5
        }
        
        self.sector_rules = {
            "Produção": {
                "horas_diarias_objetivo": 8.0,
                "tolerancia_atraso_minutos": 10,
                "hora_entrada_padrao": "08:00",
                "hora_saida_padrao": "17:00",
                "intervalo_almoco_minimo": 30,
                "max_horas_extras_dia": 3.0,
                "turnos_rotativos": True
            },
            "Administrativo": {
                "horas_diarias_objetivo": 8.0,
                "tolerancia_atraso_minutos": 15,
                "hora_entrada_padrao": "09:00",
                "hora_saida_padrao": "18:00",
                "intervalo_almoco_minimo": 60,
                "max_horas_extras_dia": 2.0,
                "horario_flexivel": True
            },
            "Vendas": {
                "horas_diarias_objetivo": 8.0,
                "tolerancia_atraso_minutos": 30,
                "hora_entrada_padrao": "09:00",
                "hora_saida_padrao": "18:00",
                "intervalo_almoco_minimo": 45,
                "max_horas_extras_dia": 4.0,
                "trabalho_fins_semana": True
            },
            "Logística": {
                "horas_diarias_objetivo": 8.0,
                "tolerancia_atraso_minutos": 5,
                "hora_entrada_padrao": "07:00",
                "hora_saida_padrao": "16:00",
                "intervalo_almoco_minimo": 30,
                "max_horas_extras_dia": 2.5,
                "turnos_especiais": True
            }
        }
    
    def get_rules(self, sector="default"):
        """Obtém as regras para um setor específico"""
        if sector in self.sector_rules:
            # Combinar regras padrão com específicas do setor
            rules = self.default_rules.copy()
            rules.update(self.sector_rules[sector])
            return rules
        return self.default_rules
    
    def analyze_compliance(self, df, sector="default"):
        """Analisa conformidade com as regras"""
        rules = self.get_rules(sector)
        analysis = {}
        
        if df.empty:
            return analysis
        
        # Filtrar apenas dias de trabalho
        work_days = df[df['dia_trabalho'] == True].copy()
        
        if work_days.empty:
            return analysis
        
        # 1. Análise de horas diárias
        analysis['horas_diarias'] = self._analyze_daily_hours(work_days, rules)
        
        # 2. Análise de pontualidade
        analysis['pontualidade'] = self._analyze_punctuality(work_days, rules)
        
        # 3. Análise de intervalos
        analysis['intervalos'] = self._analyze_breaks(work_days, rules)
        
        # 4. Análise de horas extras
        analysis['horas_extras'] = self._analyze_overtime(work_days, rules)
        
        # 5. Resumo geral
        analysis['resumo'] = self._generate_summary(work_days, rules, analysis)
        
        return analysis
    
    def _analyze_daily_hours(self, df, rules):
        """Analisa cumprimento de horas diárias"""
        target_hours = rules['horas_diarias_objetivo']
        
        # Calcular estatísticas
        total_days = len(df)
        compliant_days = len(df[df['horas_efetivas_num'] >= target_hours])
        avg_hours = df['horas_efetivas_num'].mean()
        
        # Identificar dias com déficit
        deficit_days = df[df['horas_efetivas_num'] < target_hours]
        total_deficit = (target_hours * len(deficit_days) - deficit_days['horas_efetivas_num'].sum())
        
        return {
            'total_dias': total_days,
            'dias_conformes': compliant_days,
            'percentual_conformidade': (compliant_days / total_days * 100) if total_days > 0 else 0,
            'media_horas_diarias': avg_hours,
            'deficit_total_horas': total_deficit,
            'dias_com_deficit': len(deficit_days)
        }
    
    def _analyze_punctuality(self, df, rules):
        """Analisa pontualidade"""
        tolerance_minutes = rules['tolerancia_atraso_minutos']
        standard_entry = rules['hora_entrada_padrao']
        
        # Calcular atrasos
        delays = []
        for _, row in df.iterrows():
            if row['primeiro_e1']:
                try:
                    entry_time = datetime.strptime(row['primeiro_e1'], '%H:%M').time()
                    standard_time = datetime.strptime(standard_entry, '%H:%M').time()
                    
                    # Converter para minutos desde meia-noite para comparação
                    entry_minutes = entry_time.hour * 60 + entry_time.minute
                    standard_minutes = standard_time.hour * 60 + standard_time.minute
                    
                    delay = entry_minutes - standard_minutes
                    delays.append(max(0, delay))  # Só contar atrasos positivos
                except:
                    continue
        
        if delays:
            late_days = len([d for d in delays if d > tolerance_minutes])
            avg_delay = sum(delays) / len(delays)
            max_delay = max(delays)
        else:
            late_days = 0
            avg_delay = 0
            max_delay = 0
        
        return {
            'total_dias_analisados': len(delays),
            'dias_com_atraso': late_days,
            'percentual_pontualidade': ((len(delays) - late_days) / len(delays) * 100) if delays else 100,
            'atraso_medio_minutos': avg_delay,
            'maior_atraso_minutos': max_delay,
            'tolerancia_configurada': tolerance_minutes
        }
    
    def _analyze_breaks(self, df, rules):
        """Analisa intervalos e pausas"""
        min_lunch_break = rules['intervalo_almoco_minimo']
        
        # Esta análise seria mais complexa com os dados de E1,S1,E2,S2, etc.
        # Por agora, retornar estrutura básica
        return {
            'intervalo_minimo_configurado': min_lunch_break,
            'analise_disponivel': False,  # Implementar com mais dados
            'observacoes': 'Análise detalhada de intervalos requer processamento adicional dos horários'
        }
    
    def _analyze_overtime(self, df, rules):
        """Analisa horas extras"""
        target_hours = rules['horas_diarias_objetivo']
        max_overtime = rules['max_horas_extras_dia']
        
        # Calcular horas extras
        df_overtime = df[df['horas_efetivas_num'] > target_hours].copy()
        df_overtime['horas_extras'] = df_overtime['horas_efetivas_num'] - target_hours
        
        # Dias com excesso de horas extras
        excessive_overtime = df_overtime[df_overtime['horas_extras'] > max_overtime]
        
        return {
            'dias_com_horas_extras': len(df_overtime),
            'total_horas_extras': df_overtime['horas_extras'].sum() if not df_overtime.empty else 0,
            'media_horas_extras': df_overtime['horas_extras'].mean() if not df_overtime.empty else 0,
            'dias_excesso_limite': len(excessive_overtime),
            'limite_configurado': max_overtime
        }
    
    def _generate_summary(self, df, rules, analysis):
        """Gera resumo geral da análise"""
        total_work_days = len(df)
        total_hours = df['horas_efetivas_num'].sum()
        expected_hours = total_work_days * rules['horas_diarias_objetivo']
        
        # Calcular score de conformidade
        punctuality_score = analysis['pontualidade']['percentual_pontualidade']
        hours_score = analysis['horas_diarias']['percentual_conformidade']
        
        overall_score = (punctuality_score + hours_score) / 2
        
        # Determinar status
        if overall_score >= 90:
            status = "Excelente"
        elif overall_score >= 75:
            status = "Bom"
        elif overall_score >= 60:
            status = "Regular"
        else:
            status = "Necessita Melhoria"
        
        return {
            'total_dias_trabalho': total_work_days,
            'total_horas_trabalhadas': total_hours,
            'total_horas_esperadas': expected_hours,
            'diferenca_horas': total_hours - expected_hours,
            'score_conformidade': overall_score,
            'status_geral': status,
            'recomendacoes': self._generate_recommendations(analysis, rules)
        }
    
    def _generate_recommendations(self, analysis, rules):
        """Gera recomendações baseadas na análise"""
        recommendations = []
        
        # Recomendações sobre pontualidade
        if analysis['pontualidade']['percentual_pontualidade'] < 80:
            recommendations.append("Melhorar pontualidade na entrada")
        
        # Recomendações sobre horas
        if analysis['horas_diarias']['percentual_conformidade'] < 90:
            recommendations.append("Atenção ao cumprimento das horas diárias")
        
        # Recomendações sobre horas extras
        if analysis['horas_extras']['dias_excesso_limite'] > 0:
            recommendations.append("Controlar horas extras excessivas")
        
        if not recommendations:
            recommendations.append("Manter o bom desempenho atual")
        
        return recommendations
    
    def export_rules(self, sector, filename=None):
        """Exporta regras para arquivo JSON"""
        rules = self.get_rules(sector)
        
        if filename is None:
            filename = f"rules_{sector}_{datetime.now().strftime('%Y%m%d')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def import_rules(self, filename, sector):
        """Importa regras de arquivo JSON"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            
            # Validar regras básicas
            required_keys = ['horas_diarias_objetivo', 'tolerancia_atraso_minutos']
            if all(key in rules for key in required_keys):
                self.sector_rules[sector] = rules
                return True
            else:
                return False
        except:
            return False 
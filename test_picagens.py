import pandas as pd
import sys
sys.path.append('.')
from utils.csv_processor import CSVProcessor

# Testar com o ficheiro Hugo Maio.csv
processor = CSVProcessor()

# Simular file upload
class MockFile:
    def __init__(self, filepath):
        self.filepath = filepath
        
    def read(self):
        with open(self.filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def seek(self, pos):
        pass

# Processar o ficheiro
mock_file = MockFile('Hugo Maio.csv')
df = processor.load_and_process_csv(mock_file)

print('=== TESTE DE PICAGENS ===')
print()

# Verificar se as novas colunas foram adicionadas
if 'picagens_validas' in df.columns and 'aviso_picagens' in df.columns:
    print('✅ Colunas de validação adicionadas com sucesso')
else:
    print('❌ Colunas de validação não encontradas')
    print('Colunas disponíveis:', list(df.columns))

print()

# Verificar picagens válidas vs inválidas
if 'picagens_validas' in df.columns:
    valid_punches = df[df['picagens_validas'] == True]
    invalid_punches = df[df['picagens_validas'] == False]
    
    print(f'📊 Total de linhas: {len(df)}')
    print(f'✅ Picagens válidas: {len(valid_punches)}')
    print(f'❌ Picagens inválidas: {len(invalid_punches)}')
    
    if not invalid_punches.empty:
        print('\n⚠️ Linhas com problemas:')
        for idx, row in invalid_punches.iterrows():
            print(f'  - {row["Data"].strftime("%d/%m/%Y")}: {row["aviso_picagens"]}')

print()

# Verificar uma linha específica com 4 picagens
normal_rows = df[df['Tipo'] == 'Normal']
if not normal_rows.empty:
    print('=== EXEMPLO DE LINHA NORMAL (4 PICAGENS) ===')
    sample_row = normal_rows.iloc[0]
    print(f'Data: {sample_row["Data"].strftime("%d/%m/%Y")}')
    print(f'E1: {sample_row["E1"]} (Entrada inicial)')
    print(f'S1: {sample_row["S1"]} (Saída almoço)')
    print(f'E2: {sample_row["E2"]} (Entrada almoço)')
    print(f'S2: {sample_row["S2"]} (Saída final)')
    print(f'E3: {sample_row["E3"]} (deve ser 00:00)')
    print(f'S3: {sample_row["S3"]} (deve ser 00:00)')
    print(f'E4: {sample_row["E4"]} (deve ser 00:00)')
    print(f'S4: {sample_row["S4"]} (deve ser 00:00)')
    print(f'Válida: {sample_row["picagens_validas"]}')
    print(f'Aviso: {sample_row["aviso_picagens"]}')

print()
print('=== RESUMO ===')
print('A nova lógica deve:')
print('1. ✅ Distribuir 4 picagens como E1-S1-E2-S2')
print('2. ✅ Marcar E3, S3, E4, S4 como 00:00')
print('3. ✅ Validar picagens e mostrar avisos')
print('4. ✅ Não contar linhas com picagens inválidas nos cálculos') 
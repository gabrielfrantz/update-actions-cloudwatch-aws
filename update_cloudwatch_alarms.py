#!/usr/bin/env python3
"""
Script para adicionar ou remover tópicos SNS das actions dos alarmes do CloudWatch.

Uso:
    python update_cloudwatch_alarms.py --list-alarms alarms.json --action add --states OK,IN_ALARM --topic-arn arn:aws:sns:...
"""

import json
import sys
import argparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Set, Tuple


class CloudWatchAlarmUpdater:
    """Classe para atualizar ações SNS dos alarmes do CloudWatch."""
    
    # Estados válidos dos alarmes
    VALID_STATES = ['OK', 'IN_ALARM', 'INSUFFICIENT_DATA']
    
    def __init__(self, dry_run: bool = False):
        """
        Inicializa o atualizador de alarmes.
        
        Args:
            dry_run: Se True, apenas simula as operações sem fazer alterações
        """
        self.dry_run = dry_run
        self._init_aws_client()
        
    def _init_aws_client(self):
        """Inicializa o cliente boto3 do CloudWatch usando credenciais do ambiente."""
        try:
            # Usar credenciais do ambiente (configuradas pelo workflow do GitHub Actions)
            self.cloudwatch = boto3.client('cloudwatch')
            print("✓ Usando credenciais do ambiente AWS")
                
        except NoCredentialsError:
            print("✗ Erro: Credenciais AWS não encontradas")
            print("  Certifique-se de que as credenciais foram configuradas pelo workflow")
            sys.exit(1)
        except ClientError as e:
            print(f"✗ Erro ao inicializar cliente CloudWatch: {e}")
            sys.exit(1)
    
    def load_alarm_list(self, json_path: str) -> List[str]:
        """
        Carrega lista de alarmes de um arquivo JSON.
        
        Args:
            json_path: Caminho para o arquivo JSON com a lista de alarmes
            
        Returns:
            Lista de nomes dos alarmes
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Suporta tanto lista direta quanto objeto com chave 'alarms'
            if isinstance(data, list):
                alarms = data
            elif isinstance(data, dict) and 'alarms' in data:
                alarms = data['alarms']
            else:
                raise ValueError("Formato JSON inválido. Esperado lista ou objeto com chave 'alarms'")
            
            # Remove duplicatas e ordena
            alarms = sorted(list(set(alarms)))
            print(f"✓ Carregados {len(alarms)} alarmes únicos de {json_path}")
            return alarms
            
        except FileNotFoundError:
            print(f"✗ Erro: Arquivo {json_path} não encontrado")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"✗ Erro ao decodificar JSON: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"✗ Erro ao carregar lista de alarmes: {e}")
            sys.exit(1)
    
    def get_alarm_details(self, alarm_names: List[str]) -> Tuple[Dict[str, Dict], List[str]]:
        """
        Busca detalhes dos alarmes no CloudWatch.
        
        Args:
            alarm_names: Lista de nomes dos alarmes
            
        Returns:
            Tupla contendo:
            - Dicionário com nome do alarme como chave e detalhes como valor
            - Lista de alarmes não encontrados
        """
        alarms_details = {}
        not_found = []
        
        # CloudWatch permite buscar até 100 alarmes por vez
        batch_size = 100
        for i in range(0, len(alarm_names), batch_size):
            batch = alarm_names[i:i + batch_size]
            
            try:
                response = self.cloudwatch.describe_alarms(
                    AlarmNames=batch
                )
                
                for alarm in response['MetricAlarms']:
                    alarm_name = alarm['AlarmName']
                    alarms_details[alarm_name] = {
                        'AlarmName': alarm_name,
                        'AlarmArn': alarm.get('AlarmArn', ''),
                        'OKActions': alarm.get('OKActions', []),
                        'AlarmActions': alarm.get('AlarmActions', []),
                        'InsufficientDataActions': alarm.get('InsufficientDataActions', [])
                    }
                
                # Verificar alarmes não encontrados
                found_names = {a['AlarmName'] for a in response['MetricAlarms']}
                not_found.extend([name for name in batch if name not in found_names])
                
            except ClientError as e:
                print(f"✗ Erro ao buscar alarmes: {e}")
                sys.exit(1)
        
        return alarms_details, not_found
    
    def update_alarm_sns_topic(self, alarm_name: str, topic_arn: str, 
                               states: List[str], action: str) -> Dict:
        """
        Adiciona ou remove um tópico SNS de um alarme específico.
        
        Args:
            alarm_name: Nome do alarme
            topic_arn: ARN do tópico SNS
            states: Lista de estados onde aplicar a ação (OK, IN_ALARM, INSUFFICIENT_DATA)
            action: 'add' para adicionar, 'remove' para remover
            
        Returns:
            Dicionário com informações sobre a atualização:
            - 'success': bool indicando sucesso
            - 'changes': lista de mudanças realizadas por estado
            - 'error': mensagem de erro (se houver)
        """
        result = {
            'success': False,
            'changes': [],
            'error': None
        }
        
        try:
            # Buscar alarme atual
            response = self.cloudwatch.describe_alarms(AlarmNames=[alarm_name])
            
            if not response['MetricAlarms']:
                result['error'] = f"Alarme '{alarm_name}' não encontrado"
                return result
            
            alarm = response['MetricAlarms'][0]
            
            # Preparar ações por estado
            ok_actions = set(alarm.get('OKActions', []))
            alarm_actions = set(alarm.get('AlarmActions', []))
            insufficient_data_actions = set(alarm.get('InsufficientDataActions', []))
            
            # Aplicar ação para cada estado e registrar mudanças
            updated = False
            if 'OK' in states:
                if action == 'add' and topic_arn not in ok_actions:
                    ok_actions.add(topic_arn)
                    updated = True
                    result['changes'].append('OK: Adicionado tópico SNS')
                elif action == 'remove' and topic_arn in ok_actions:
                    ok_actions.remove(topic_arn)
                    updated = True
                    result['changes'].append('OK: Removido tópico SNS')
                elif action == 'add' and topic_arn in ok_actions:
                    result['changes'].append('OK: Tópico já presente (nenhuma ação)')
                elif action == 'remove' and topic_arn not in ok_actions:
                    result['changes'].append('OK: Tópico não presente (nenhuma ação)')
            
            if 'IN_ALARM' in states:
                if action == 'add' and topic_arn not in alarm_actions:
                    alarm_actions.add(topic_arn)
                    updated = True
                    result['changes'].append('IN_ALARM: Adicionado tópico SNS')
                elif action == 'remove' and topic_arn in alarm_actions:
                    alarm_actions.remove(topic_arn)
                    updated = True
                    result['changes'].append('IN_ALARM: Removido tópico SNS')
                elif action == 'add' and topic_arn in alarm_actions:
                    result['changes'].append('IN_ALARM: Tópico já presente (nenhuma ação)')
                elif action == 'remove' and topic_arn not in alarm_actions:
                    result['changes'].append('IN_ALARM: Tópico não presente (nenhuma ação)')
            
            if 'INSUFFICIENT_DATA' in states:
                if action == 'add' and topic_arn not in insufficient_data_actions:
                    insufficient_data_actions.add(topic_arn)
                    updated = True
                    result['changes'].append('INSUFFICIENT_DATA: Adicionado tópico SNS')
                elif action == 'remove' and topic_arn in insufficient_data_actions:
                    insufficient_data_actions.remove(topic_arn)
                    updated = True
                    result['changes'].append('INSUFFICIENT_DATA: Removido tópico SNS')
                elif action == 'add' and topic_arn in insufficient_data_actions:
                    result['changes'].append('INSUFFICIENT_DATA: Tópico já presente (nenhuma ação)')
                elif action == 'remove' and topic_arn not in insufficient_data_actions:
                    result['changes'].append('INSUFFICIENT_DATA: Tópico não presente (nenhuma ação)')
            
            if not updated and not result['changes']:
                result['error'] = 'Nenhuma alteração necessária'
                return result
            
            # Atualizar alarme (se não for dry-run e houver mudanças)
            if not self.dry_run and updated:
                # Construir parâmetros do alarme preservando todos os campos originais
                put_params = {
                    'AlarmName': alarm_name,
                    'MetricName': alarm['MetricName'],
                    'Namespace': alarm['Namespace'],
                    'Period': alarm['Period'],
                    'EvaluationPeriods': alarm['EvaluationPeriods'],
                    'Threshold': alarm['Threshold'],
                    'ComparisonOperator': alarm['ComparisonOperator'],
                    'OKActions': list(ok_actions),
                    'AlarmActions': list(alarm_actions),
                    'InsufficientDataActions': list(insufficient_data_actions),
                }
                
                # Campos opcionais que podem estar presentes
                if 'Statistic' in alarm:
                    put_params['Statistic'] = alarm['Statistic']
                if 'ExtendedStatistic' in alarm:
                    put_params['ExtendedStatistic'] = alarm['ExtendedStatistic']
                if 'Unit' in alarm:
                    put_params['Unit'] = alarm['Unit']
                if 'AlarmDescription' in alarm:
                    put_params['AlarmDescription'] = alarm['AlarmDescription']
                if 'TreatMissingData' in alarm:
                    put_params['TreatMissingData'] = alarm['TreatMissingData']
                else:
                    put_params['TreatMissingData'] = 'missing'
                if 'Dimensions' in alarm and alarm['Dimensions']:
                    put_params['Dimensions'] = alarm['Dimensions']
                if 'DatapointsToAlarm' in alarm:
                    put_params['DatapointsToAlarm'] = alarm['DatapointsToAlarm']
                if 'ThresholdMetricId' in alarm:
                    put_params['ThresholdMetricId'] = alarm['ThresholdMetricId']
                if 'Metrics' in alarm and alarm['Metrics']:
                    put_params['Metrics'] = alarm['Metrics']
                if 'Tags' in alarm and alarm['Tags']:
                    put_params['Tags'] = alarm['Tags']
                if 'ActionsEnabled' in alarm:
                    put_params['ActionsEnabled'] = alarm['ActionsEnabled']
                
                self.cloudwatch.put_metric_alarm(**put_params)
            
            result['success'] = True
            return result
            
        except ClientError as e:
            result['error'] = f"Erro ao atualizar alarme: {e}"
            return result
        except Exception as e:
            result['error'] = f"Erro inesperado: {e}"
            return result
    
    def process_alarms(self, alarm_list_path: str, topic_arn: str, 
                      states: List[str], action: str) -> Dict:
        """
        Processa todos os alarmes da lista.
        
        Args:
            alarm_list_path: Caminho para arquivo JSON com lista de alarmes
            topic_arn: ARN do tópico SNS
            states: Lista de estados onde aplicar a ação
            action: 'add' para adicionar, 'remove' para remover
            
        Returns:
            Dicionário com estatísticas do processamento
        """
        # Validar estados
        invalid_states = [s for s in states if s not in self.VALID_STATES]
        if invalid_states:
            print(f"✗ Estados inválidos: {', '.join(invalid_states)}")
            print(f"  Estados válidos: {', '.join(self.VALID_STATES)}")
            sys.exit(1)
        
        # Carregar lista de alarmes
        alarm_names = self.load_alarm_list(alarm_list_path)
        
        if not alarm_names:
            print("✗ Lista de alarmes está vazia")
            sys.exit(1)
        
        # Buscar detalhes dos alarmes
        print(f"\nBuscando detalhes de {len(alarm_names)} alarme(s)...")
        alarms_details, not_found_alarms = self.get_alarm_details(alarm_names)
        
        # Mostrar alarmes não encontrados
        if not_found_alarms:
            print(f"\n⚠ Aviso: {len(not_found_alarms)} alarme(s) não encontrado(s):")
            for alarm in sorted(not_found_alarms):
                print(f"  ✗ {alarm}")
            print()
        
        if not alarms_details:
            if not_found_alarms:
                print("✗ Nenhum alarme válido foi encontrado na lista fornecida")
                sys.exit(1)
            else:
                print("✗ Nenhum alarme válido encontrado")
                sys.exit(1)
        
        # Modo dry-run: apenas mostrar o que seria feito
        if self.dry_run:
            print(f"\n{'='*60}")
            print("MODO DRY-RUN - Nenhuma alteração será realizada")
            print(f"{'='*60}")
            print(f"\nTotal de alarmes encontrados: {len(alarms_details)}")
            if not_found_alarms:
                print(f"Alarmes não encontrados: {len(not_found_alarms)}")
            print(f"Ação: {action.upper()}")
            print(f"Tópico SNS: {topic_arn}")
            print(f"Estados: {', '.join(states)}")
            print(f"\nDetalhes por alarme:")
            print(f"{'-'*60}")
            
            for alarm_name in sorted(alarms_details.keys()):
                details = alarms_details[alarm_name]
                print(f"\nAlarme: {alarm_name}")
                for state in states:
                    if state == 'OK':
                        current = details['OKActions']
                        has_topic = topic_arn in current
                    elif state == 'IN_ALARM':
                        current = details['AlarmActions']
                        has_topic = topic_arn in current
                    elif state == 'INSUFFICIENT_DATA':
                        current = details['InsufficientDataActions']
                        has_topic = topic_arn in current
                    
                    if action == 'add' and not has_topic:
                        print(f"  [{state}]: Adicionar tópico SNS")
                    elif action == 'remove' and has_topic:
                        print(f"  [{state}]: Remover tópico SNS")
                    elif action == 'add' and has_topic:
                        print(f"  [{state}]: Tópico já presente (nenhuma ação)")
                    elif action == 'remove' and not has_topic:
                        print(f"  [{state}]: Tópico não presente (nenhuma ação)")
            
            print(f"\n{'-'*60}")
            print("Fim do modo dry-run")
            return {
                'total': len(alarm_names),
                'found': len(alarms_details),
                'not_found': len(not_found_alarms),
                'processed': 0,
                'success': 0,
                'failed': 0
            }
        
        # Modo execução real
        print(f"\n{'='*60}")
        print(f"Processando {len(alarms_details)} alarme(s)...")
        print(f"{'='*60}")
        print(f"Ação: {action.upper()}")
        print(f"Tópico SNS: {topic_arn}")
        print(f"Estados: {', '.join(states)}")
        print(f"{'='*60}\n")
        
        stats = {
            'total': len(alarm_names),
            'found': len(alarms_details),
            'not_found': len(not_found_alarms),
            'processed': 0,
            'success': 0,
            'failed': 0,
            'no_changes': 0
        }
        
        # Processar alarmes encontrados
        for alarm_name in sorted(alarms_details.keys()):
            print(f"Alarme: {alarm_name}")
            
            result = self.update_alarm_sns_topic(alarm_name, topic_arn, states, action)
            
            if result['error']:
                print(f"  ✗ {result['error']}")
                stats['failed'] += 1
            elif result['success']:
                # Mostrar detalhes das mudanças
                if result['changes']:
                    for change in result['changes']:
                        if 'nenhuma ação' in change.lower():
                            print(f"  ⚪ {change}")
                        elif 'Adicionado' in change:
                            print(f"  ✓ {change}")
                        elif 'Removido' in change:
                            print(f"  ✓ {change}")
                    # Verificar se houve alteração real (não apenas "nenhuma ação")
                    has_real_change = any('nenhuma ação' not in c.lower() for c in result['changes'])
                    if has_real_change:
                        stats['success'] += 1
                    else:
                        stats['no_changes'] += 1
                else:
                    print(f"  ⚪ Nenhuma alteração necessária")
                    stats['no_changes'] += 1
            else:
                print(f"  ✗ Falha ao processar")
                stats['failed'] += 1
            
            stats['processed'] += 1
            print()  # Linha em branco entre alarmes
        
        # Resumo
        print(f"{'='*60}")
        print("Resumo:")
        print(f"  Total na lista: {stats['total']}")
        print(f"  Alarmes encontrados: {stats['found']}")
        if stats['not_found'] > 0:
            print(f"  ✗ Alarmes não encontrados: {stats['not_found']}")
        print(f"  Processados: {stats['processed']}")
        print(f"  ✓ Atualizados com sucesso: {stats['success']}")
        print(f"  ⚪ Sem alterações necessárias: {stats['no_changes']}")
        if stats['failed'] > 0:
            print(f"  ✗ Falhas no processamento: {stats['failed']}")
        print(f"{'='*60}")
        
        return stats


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description='Adiciona ou remove tópicos SNS das actions dos alarmes do CloudWatch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Dry-run: ver o que seria alterado
  python update_cloudwatch_alarms.py --list-alarms alarms.json --action add \\
      --states OK,IN_ALARM --topic-arn arn:aws:sns:us-east-1:123456789012:my-topic \\
      --dry-run

  # Adicionar tópico SNS aos estados OK e IN_ALARM
  python update_cloudwatch_alarms.py --list-alarms alarms.json --action add \\
      --states OK,IN_ALARM --topic-arn arn:aws:sns:us-east-1:123456789012:my-topic

Nota: As credenciais AWS devem estar configuradas no ambiente (via variáveis de ambiente
ou pelo workflow do GitHub Actions que assume a role automaticamente).
        """
    )
    
    parser.add_argument(
        '--list-alarms',
        required=True,
        help='Caminho para arquivo JSON com lista de alarmes'
    )
    
    parser.add_argument(
        '--action',
        required=True,
        choices=['add', 'remove'],
        help='Ação a realizar: add ou remove'
    )
    
    parser.add_argument(
        '--states',
        required=True,
        help='Estados dos alarmes (separados por vírgula): OK,IN_ALARM,INSUFFICIENT_DATA'
    )
    
    parser.add_argument(
        '--topic-arn',
        required=True,
        help='ARN do tópico SNS'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Executar em modo dry-run (apenas mostrar o que seria feito)'
    )
    
    args = parser.parse_args()
    
    # Processar estados
    states = [s.strip().upper() for s in args.states.split(',')]
    
    # Validar formato do ARN do tópico
    if not args.topic_arn.startswith('arn:aws:sns:'):
        print("✗ Erro: ARN do tópico SNS inválido (deve começar com 'arn:aws:sns:')")
        sys.exit(1)
    
    # Criar atualizador e processar
    updater = CloudWatchAlarmUpdater(dry_run=args.dry_run)
    updater.process_alarms(
        alarm_list_path=args.list_alarms,
        topic_arn=args.topic_arn,
        states=states,
        action=args.action
    )


if __name__ == '__main__':
    main()


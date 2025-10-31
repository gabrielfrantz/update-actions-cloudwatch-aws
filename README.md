# Update CloudWatch Alarm SNS Topics

Este repositório contém um script Python e workflow do GitHub Actions para gerenciar tópicos SNS das actions dos alarmes do CloudWatch na AWS. Permite adicionar ou remover tópicos SNS dos estados OK, IN_ALARM e INSUFFICIENT_DATA através de uma lista JSON de alarmes.

## 📋 Funcionalidades

- ✅ Adicionar ou remover tópicos SNS dos alarmes do CloudWatch
- ✅ Seleção de estados (OK, IN_ALARM, INSUFFICIENT_DATA) via checkboxes no workflow
- ✅ Modo dry-run para visualizar alterações antes de aplicar
- ✅ Autenticação via AWS Role (assume role) configurada nos environments do GitHub
- ✅ Processamento em lote de alarmes através de lista JSON
- ✅ Validação de alarmes existentes antes da atualização

## 📁 Estrutura do Repositório

```
update-actions-cloudwatch-aws/
├── .github/
│   └── workflows/
│       └── update-cloudwatch-alarms.yml    # Workflow do GitHub Actions
├── update_cloudwatch_alarms.py             # Script Python principal
├── alarms.example.json                      # Exemplo de lista de alarmes
├── iam-permissions.json                     # Política IAM de referência
├── requirements.txt                         # Dependências Python
├── SETUP.md                                 # Guia de configuração passo a passo
└── README.md                                # Esta documentação
```

## 🚀 Configuração

> 📖 **Para um guia passo a passo detalhado, consulte o arquivo [SETUP.md](SETUP.md)**

### 1. Configuração AWS IAM

#### Criar a Role AWS

1. Acesse o console AWS IAM
2. Crie uma nova Role com as seguintes características:
   - **Tipo**: Custom trust policy
   - **Trust Policy**: Use o arquivo `iam-permissions.json` como base, substituindo:
     - `ACCOUNT_ID`: ID da sua conta AWS
     - `OWNER/REPO`: Nome do seu repositório GitHub (ex: `usuario/nome-repositorio`)

#### Permissões Necessárias da Role

A role precisa das seguintes permissões IAM:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:ListTopics",
        "sns:GetTopicAttributes"
      ],
      "Resource": "*"
    }
  ]
}
```

**Nota**: As permissões `sns:ListTopics` e `sns:GetTopicAttributes` são opcionais e usadas apenas para validação. Se desejar restringir, você pode limitar ao ARN específico do tópico SNS que será usado.

### 2. Configuração GitHub Actions

#### Criar Environments

1. Acesse **Settings** → **Environments** no seu repositório GitHub
2. Crie dois environments:
   - `development`
   - `production`

#### Configurar Secrets

Para cada environment criado, adicione uma secret:

- **Nome**: `AWS_ROLE_ARN`
- **Valor**: ARN completo da role AWS criada (ex: `arn:aws:iam::123456789012:role/CloudWatchUpdater`)

**Exemplo**:
- Environment `development` → `AWS_ROLE_ARN` = `arn:aws:iam::123456789012:role/CloudWatchUpdater-Dev`
- Environment `production` → `AWS_ROLE_ARN` = `arn:aws:iam::123456789012:role/CloudWatchUpdater-Prod`

#### Configurar OIDC Provider (se necessário)

Se ainda não configurou o OIDC provider para GitHub Actions:

1. Acesse IAM → **Identity providers**
2. Adicione provider:
   - **Provider URL**: `https://token.actions.githubusercontent.com`
   - **Audience**: `sts.amazonaws.com`

### 3. Criar Lista de Alarmes

Crie um arquivo JSON no repositório com a lista de alarmes a serem processados:

```json
{
  "alarms": [
    "HighCPUUtilization",
    "LowDiskSpace",
    "DatabaseConnectionErrors",
    "ApplicationErrors"
  ]
}
```

Ou formato simplificado (lista direta):

```json
[
  "HighCPUUtilization",
  "LowDiskSpace",
  "DatabaseConnectionErrors"
]
```

**Nota**: O arquivo `alarms.example.json` serve como exemplo.

## 📖 Uso

### Via GitHub Actions (Recomendado)

1. Acesse a aba **Actions** no repositório
2. Selecione o workflow **Update CloudWatch Alarm SNS Topics**
3. Clique em **Run workflow**
4. Preencha os inputs:
   - **Environment**: `development` ou `production`
   - **Alarm list file**: Caminho para o arquivo JSON (ex: `alarms.json`)
   - **Topic ARN**: ARN completo do tópico SNS
   - **Action**: `add` ou `remove`
   - **State OK**: ☑️ (checkbox) - para aplicar no estado OK
   - **State IN_ALARM**: ☑️ (checkbox) - para aplicar no estado IN_ALARM
   - **State INSUFFICIENT_DATA**: ☑️ (checkbox) - para aplicar no estado INSUFFICIENT_DATA
   - **Dry-run**: ☑️ (recomendado marcar primeiro para visualizar)

5. Execute o workflow

**Dica**: Sempre execute primeiro com `dry-run` marcado para visualizar o que será alterado!

### Via Linha de Comando (Local)

#### Instalação

```bash
pip install -r requirements.txt
```

#### Uso

```bash
# Dry-run: visualizar alterações sem aplicar
python update_cloudwatch_alarms.py \
  --list-alarms alarms.json \
  --action add \
  --states OK,IN_ALARM \
  --topic-arn arn:aws:sns:us-east-1:123456789012:my-topic \
  --dry-run

# Executar alteração real
python update_cloudwatch_alarms.py \
  --list-alarms alarms.json \
  --action add \
  --states OK,IN_ALARM,INSUFFICIENT_DATA \
  --topic-arn arn:aws:sns:us-east-1:123456789012:my-topic
```

**Nota**: No GitHub Actions, as credenciais são configuradas automaticamente pelo workflow que assume a role AWS via OIDC.

#### Parâmetros

| Parâmetro | Obrigatório | Descrição |
|-----------|-------------|-----------|
| `--list-alarms` | ✅ | Caminho para arquivo JSON com lista de alarmes |
| `--action` | ✅ | Ação: `add` ou `remove` |
| `--states` | ✅ | Estados separados por vírgula: `OK,IN_ALARM,INSUFFICIENT_DATA` |
| `--topic-arn` | ✅ | ARN completo do tópico SNS |
| `--dry-run` | ❌ | Flag para modo dry-run (sem alterações) |

**Nota**: O script usa as credenciais AWS configuradas no ambiente. No GitHub Actions, o workflow assume a role automaticamente.

## 🔒 Segurança

- ✅ Autenticação via AWS Role (assumida automaticamente pelo workflow do GitHub Actions via OIDC)
- ✅ Permissões mínimas necessárias (princípio do menor privilégio)
- ✅ Suporte a múltiplos environments (development/production)
- ✅ Modo dry-run para validação antes de alterações
- ✅ Validação de formatos (ARN, estados)

## 📝 Exemplos

### Exemplo 1: Adicionar tópico SNS ao estado OK

```bash
python update_cloudwatch_alarms.py \
  --list-alarms alarms.json \
  --action add \
  --states OK \
  --topic-arn arn:aws:sns:us-east-1:123456789012:notifications
```

### Exemplo 2: Remover tópico SNS de todos os estados

```bash
python update_cloudwatch_alarms.py \
  --list-alarms alarms.json \
  --action remove \
  --states OK,IN_ALARM,INSUFFICIENT_DATA \
  --topic-arn arn:aws:sns:us-east-1:123456789012:old-topic
```

### Exemplo 3: Dry-run completo

```bash
python update_cloudwatch_alarms.py \
  --list-alarms alarms.json \
  --action add \
  --states OK,IN_ALARM \
  --topic-arn arn:aws:sns:us-east-1:123456789012:new-topic \
  --dry-run
```

## ⚠️ Considerações Importantes

1. **Dry-run sempre primeiro**: Sempre execute em modo dry-run antes de fazer alterações reais
2. **Backup**: Considere fazer backup das configurações dos alarmes críticos antes de alterações em massa
3. **Validação**: O script valida se os alarmes existem antes de processar
4. **Duplicatas**: A lista JSON remove automaticamente alarmes duplicados
5. **Limites**: O CloudWatch permite buscar até 100 alarmes por vez (o script processa em lotes automaticamente)

## 🐛 Troubleshooting

### Erro: "Credenciais AWS não encontradas"
- Verifique se a role ARN está configurada corretamente no secret do environment
- Confirme que o OIDC provider está configurado no IAM

### Erro: "Alarme não encontrado"
- Verifique se o nome do alarme na lista JSON está correto
- Confirme que você tem permissão para acessar o alarme na conta/região AWS

### Erro: "Estados inválidos"
- Use apenas: `OK`, `IN_ALARM`, `INSUFFICIENT_DATA`
- Separe múltiplos estados por vírgula: `OK,IN_ALARM`

### Erro: "Formato JSON inválido"
- Verifique a sintaxe do arquivo JSON
- Use o arquivo `alarms.example.json` como referência

## 📄 Licença

Este projeto está disponível para uso interno.

## 🤝 Contribuindo

1. Faça fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas alterações (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📞 Suporte

Para dúvidas ou problemas, abra uma issue no repositório.

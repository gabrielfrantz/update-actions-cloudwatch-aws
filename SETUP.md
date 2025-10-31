# Guia de Configuração Completa

Este guia detalha passo a passo a configuração necessária para usar este repositório.

## 📋 Pré-requisitos

- Conta AWS com permissões para criar IAM Roles e Policies
- Repositório GitHub com GitHub Actions habilitado
- Conhecimento básico de AWS IAM e CloudWatch

## 🔐 Passo 1: Configurar OIDC Provider no AWS (se ainda não configurado)

Se você já tem um OIDC provider configurado para GitHub Actions, pule para o Passo 2.

1. Acesse o console AWS IAM
2. No menu lateral, clique em **Identity providers**
3. Clique em **Add provider**
4. Configure:
   - **Provider type**: OpenID Connect
   - **Provider URL**: `https://token.actions.githubusercontent.com`
   - **Audience**: `sts.amazonaws.com`
5. Clique em **Add provider**

## 🛡️ Passo 2: Criar IAM Role

1. Acesse o console AWS IAM
2. No menu lateral, clique em **Roles**
3. Clique em **Create role**
4. Selecione **Web identity**
5. Selecione o provider que você criou (ou já existente) com URL `token.actions.githubusercontent.com`
6. Em **Audience**, selecione `sts.amazonaws.com`
7. Clique em **Next**

### Configurar Condições (Trust Policy)

Na seção de condições, você pode configurar:

**Opção 1: Permitir para todo o repositório (recomendado para testes)**
```json
{
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
  },
  "StringLike": {
    "token.actions.githubusercontent.com:sub": "repo:SEU_USUARIO/SEU_REPOSITORIO:*"
  }
}
```

**Opção 2: Permitir apenas para branch específica**
```json
{
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub": "repo:SEU_USUARIO/SEU_REPOSITORIO:ref:refs/heads/main"
  }
}
```

**Opção 3: Permitir apenas para environment específico**
```json
{
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
  },
  "StringLike": {
    "token.actions.githubusercontent.com:sub": "repo:SEU_USUARIO/SEU_REPOSITORIO:environment:development"
  }
}
```

Substitua:
- `SEU_USUARIO`: Seu nome de usuário ou organização no GitHub
- `SEU_REPOSITORIO`: Nome do repositório

8. Clique em **Next**

### Anexar Permissões (Permissions Policy)

1. Clique em **Create policy**
2. Selecione a aba **JSON**
3. Cole a seguinte política (ou use o arquivo `iam-permissions.json` como referência):

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

4. Clique em **Next**
5. Dê um nome à policy (ex: `CloudWatchAlarmSNSUpdater`)
6. Clique em **Create policy**
7. Volte para a criação da role, atualize a lista de policies e selecione a policy criada
8. Clique em **Next**

### Configurar Role

9. Dê um nome à role (ex: `GitHubActions-CloudWatchUpdater`)
10. Adicione uma descrição (opcional): "Role para GitHub Actions atualizar tópicos SNS dos alarmes CloudWatch"
11. Clique em **Create role**

### Anotar o ARN da Role

12. Após criar a role, anote o **ARN completo** (ex: `arn:aws:iam::123456789012:role/GitHubActions-CloudWatchUpdater`)

## 🌍 Passo 3: Criar Environments no GitHub

1. Acesse seu repositório no GitHub
2. Vá em **Settings** → **Environments**
3. Clique em **New environment**
4. Crie dois environments:
   - Nome: `development`
   - Nome: `production`

## 🔑 Passo 4: Configurar Secrets nos Environments

Para cada environment criado:

1. Clique no environment (`development` ou `production`)
2. Na seção **Secrets**, clique em **Add secret**
3. Configure:
   - **Name**: `AWS_ROLE_ARN`
   - **Value**: ARN completo da role AWS criada
   
   **Nota**: Você pode usar roles diferentes para cada environment:
   - `development`: `arn:aws:iam::123456789012:role/GitHubActions-CloudWatchUpdater-Dev`
   - `production`: `arn:aws:iam::123456789012:role/GitHubActions-CloudWatchUpdater-Prod`

4. Clique em **Add secret**

## 📝 Passo 5: Criar Arquivo de Lista de Alarmes

1. No seu repositório, crie um arquivo JSON (ex: `alarms.json`) na raiz
2. Adicione a lista de alarmes (use `alarms.example.json` como referência):

```json
{
  "alarms": [
    "HighCPUUtilization",
    "LowDiskSpace",
    "DatabaseConnectionErrors"
  ]
}
```

3. Commit e push do arquivo

## ✅ Passo 6: Testar o Workflow

1. Acesse a aba **Actions** no seu repositório
2. Selecione o workflow **Update CloudWatch Alarm SNS Topics**
3. Clique em **Run workflow**
4. Configure:
   - **Environment**: `development`
   - **Alarm list file**: `alarms.json`
   - **Topic ARN**: ARN do tópico SNS de teste
   - **Action**: `add`
   - Marque pelo menos um estado (OK, IN_ALARM ou INSUFFICIENT_DATA)
   - **Dry-run**: ✅ (marcado para teste seguro)
5. Clique em **Run workflow**
6. Verifique os logs para confirmar que está funcionando

## 🔍 Troubleshooting

### Erro: "Not authorized to perform sts:AssumeRoleWithWebIdentity"

- Verifique se o OIDC provider está configurado corretamente
- Confirme que a trust policy da role está permitindo o repositório correto
- Verifique se o ARN da role no secret está correto

### Erro: "Access Denied" ao acessar CloudWatch

- Verifique se a policy da role tem as permissões necessárias
- Confirme que você está usando o environment correto com o secret correto

### Alarme não encontrado

- Verifique se o nome do alarme na lista JSON está exatamente como aparece no CloudWatch
- Confirme que você tem acesso à região AWS onde o alarme está configurado

## 📚 Próximos Passos

Após a configuração inicial:

1. Teste em modo dry-run antes de fazer alterações reais
2. Considere criar roles separadas para desenvolvimento e produção
3. Revise regularmente as permissões da role (princípio do menor privilégio)
4. Monitore os logs do workflow para detectar problemas


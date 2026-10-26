# Pulso iPhone

Gestão de estoque, vendas, clientes e financeiro em português. Interface baseada no HTML original fornecido pelo usuário, com servidor Python, SQLite local e PostgreSQL externo opcional. O modo PostgreSQL instala as dependências de requirements.txt.

## Iniciar

Com Python 3.12 ou superior:

```sh
cd /workspace/Vendas-de-iphones-e-outros
python3 server.py
```

O servidor escuta em 127.0.0.1:8000. `PORT`, `PULSO_HOST` e `PULSO_DB` podem configurar porta, interface e caminho do banco. No primeiro acesso, crie seu usuário e senha (mínimo 10 caracteres). Não existe senha padrão. A primeira pessoa que acessar um banco novo define a conta: faça isso antes de expor o serviço.

A aplicação deve ser aberta pelo servidor; abrir o HTML diretamente não funciona nesta versão. Para disponibilizar na internet, use hospedagem persistente e proxy HTTPS, configure `PULSO_SECURE_COOKIE=1` e proteja o acesso ao servidor de origem. O servidor incluído é destinado ao desenvolvimento e uso local; publicação pública exige implantação própria.

## Recursos

- Login, logout, senha com hash scrypt, sessão de 12 horas, proteção CSRF e limite de tentativas de login.
- Cadastro individual de aparelhos, bateria, IMEI único, fornecedor, data de entrada e observações; reserva no cadastro e liberação de reservados.
- Venda vinculada ao estoque e cliente, taxa em reais, garantia e observações.
- Valor recebido, saldo a receber e registro de recebimentos parciais.
- Dashboard com filtros, faturamento, lucro estimado, estoque e modelos vendidos.
- Despesas e backup JSON com validação no servidor.
- Controle de revisão para impedir sobrescrita silenciosa por outra aba.

O lucro estimado é venda menos custo, taxa e despesas; não é fluxo de caixa e não inclui tributos não registrados. O gráfico mostra sempre os últimos sete dias, respeitando os filtros. Não há agenda de parcelas com vencimentos, recuperação de senha por e-mail, múltiplos usuários, cancelamento de vendas ou integração WhatsApp.

## Dados e backups

O banco fica em `.data/pulso.sqlite3`, ignorado pelo Git. Faça backup independente do banco e exporte os registros na aba Financeiro. O JSON contém os registros comerciais, sem senha ou sessões. Importar substitui os registros existentes após confirmação. Para migrar o HTML antigo, exporte o backup no navegador antigo e importe na nova versão. Os dados locais antigos não são enviados automaticamente.

## Verificação

```sh
python3 -m unittest discover -s tests -v
```

A suíte usa banco e servidor temporários e verifica login, bloqueio sem sessão, CSRF, validação, conflitos entre revisões e persistência após novo login. O fluxo completo de cadastro, venda, despesas, backup e recebimento parcial também foi exercitado em Chromium durante a implementação.

## Render gratuito + PostgreSQL externo (Neon)

Nesta modalidade, conta, senha protegida por hash, sessões e registros são guardados no PostgreSQL externo. O disco efêmero do Render não é usado para esses dados. SQLite continua disponível para desenvolvimento local. O aplicativo recusa iniciar no Render sem `DATABASE_URL`, evitando perda silenciosa de registros. As tabelas são criadas automaticamente, sem substituir dados existentes.

1. Crie um projeto no plano **Free** do Neon e obtenha a connection string PostgreSQL no botão **Connect**. Prefira a conexão com pooling. Não envie esse endereço por chat ou commit: ele contém a senha do banco.
2. No Render, selecione Python 3, branch `main`, instância **Free**, sem disco pago.
3. Build Command: `pip install -r requirements.txt && python -m unittest discover -s tests -v`
4. Start Command: `PULSO_HOST=0.0.0.0 python server.py`
5. Configure as variáveis no Render:
   - `DATABASE_URL`: connection string fornecida pelo Neon, mantida apenas no servidor.
   - `PULSO_SECURE_COOKIE`: `1`.
   - `PULSO_SETUP_TOKEN`: código longo e aleatório escolhido por você, necessário apenas para criar a primeira conta. Guarde-o com segurança e informe-o na tela de primeiro acesso.
6. Se houver campo de health check, use `/health`.
7. Publique e crie seu usuário e senha. Exporte backup JSON regularmente. Para migrar registros locais, exporte no sistema antigo e importe no novo; a conta deverá ser criada no banco novo.

As conexões PostgreSQL verificam certificado e hostname com TLS (`verify-full`). Não desative essa verificação. Não cadastre a URL do banco como segredo de proxy HTTP: a conexão PostgreSQL é TCP. `PULSO_DATABASE_CA` é um caminho opcional para CA própria, usado apenas em testes locais; no Render o padrão é o pacote de CAs do sistema.

Os planos gratuitos têm limites, podem suspender serviços por inatividade e podem mudar. O primeiro acesso após inatividade pode demorar. Confira os termos atuais no cadastro do Neon e Render; não habilite plano pago para seguir este procedimento. Essa opção não promete disponibilidade contínua nem capacidade ilimitada.

Os testes padrão nunca usam o `DATABASE_URL` de produção. Para integração, aponte **somente para um banco de teste vazio**, pois criará uma conta e dados: `PULSO_TEST_DATABASE_URL=... python -m unittest discover -s tests -v`. A integração foi executada com PostgreSQL 17 real e TLS, incluindo reinício do processo e preservação de sessão, conta e venda parcial.


## Edição de registros e taxas

Use **Editar** nas listas de Estoque, Vendas, Clientes e despesas do Financeiro. Os formulários abrem com os valores atuais e permitem cancelar sem salvar. Alterar nome de cliente atualiza as vendas vinculadas. Corrigir modelo/custo de aparelho vendido atualiza sua venda e o lucro; o status permanece Vendido. Ao corrigir o aparelho de uma venda, o anterior volta a Disponível e o novo fica Vendido. Não há exclusão de registros nesta atualização.

Na venda, escolha Pix, dinheiro, débito, crédito ou link. O modo **Automático pela tabela** calcula o desconto sobre o valor cobrado no cartão; o campo **Valor no cartão** permite separar uma entrada por Pix. Em crédito/link, selecione 1 a 12 parcelas. A prévia mostra taxa, líquido e lucro. A taxa não é repassada automaticamente ao comprador. As parcelas são informativas, sem agenda automática de vencimentos. Os recebimentos continuam em valor bruto.

A tabela em `rates.json` foi transcrita da imagem fornecida pelo usuário (26/10/2026); não consulta a operadora. Visa/Mastercard têm débito 1,37%; Elo 2,58%. Débito Amex/Hipercard não foi informado: o modo automático bloqueia esse caso. Link só tem crédito. A tabela completa está no formulário de venda e no Financeiro. Para condições diferentes, escolha **Manual em reais**. O servidor valida as taxas automáticas; vendas antigas sem metadados continuam como manuais, preservando a taxa existente. Faça backup antes de corrigir registros em lote.

Validação: suíte HTTP cobre todas as bandeiras e as 12 parcelas, débitos, taxa adulterada, parcelas inválidas, backups antigos e persistência das correções. Chromium foi usado para testar edição dos quatro cadastros, custo/modelo vinculados, taxa manual, valor parcial no cartão e formulário em tela de celular. Nenhum teste usa o banco de produção.
